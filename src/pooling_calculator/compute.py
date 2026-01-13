"""
Computation engine for Pooling Calculator.

This module handles:
- Molarity calculations (ng/µl → nM)
- Volume distribution for weighted pooling
- Project-level aggregation
- Sanity checks and flags

Architecture note: Functions are designed to be modular and composable,
allowing future extension to hierarchical/multi-stage pooling workflows.
"""

import pandas as pd

from pooling_calculator.config import (
    MW_PER_BP,
    MIN_TOTAL_VOLUME_UL,
    WARN_LOW_TOTAL_VOLUME_UL,
)


def compute_molarity_from_concentration(
    concentration_ng_ul: float,
    fragment_size_bp: float
) -> float:
    """
    Convert mass concentration to molar concentration.

    Formula: C_nM = (C_ng/µl × 10^6) / (660 g/mol/bp × L_bp)

    Args:
        concentration_ng_ul: Concentration in ng/µl
        fragment_size_bp: Fragment length in base pairs

    Returns:
        Molarity in nM

    Raises:
        ValueError: If inputs are invalid
    """
    if concentration_ng_ul <= 0:
        raise ValueError(f"Concentration must be > 0, got {concentration_ng_ul}")
    if fragment_size_bp <= 0:
        raise ValueError(f"Fragment size must be > 0, got {fragment_size_bp}")

    # Convert ng/µl to nM
    # ng/µl → g/L: multiply by 1
    # g/L → mol/L: divide by MW (g/mol)
    # mol/L → nmol/L (nM): multiply by 10^9
    # But ng/µl = µg/mL, so we need: (ng/µl × 10^6) / (MW_g/mol)

    molarity_nm = (concentration_ng_ul * 1_000_000) / (MW_PER_BP * fragment_size_bp)

    return molarity_nm


def compute_effective_molarity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute effective molarity for each library.

    Uses empirical nM if provided, otherwise calculates from concentration
    and fragment size. Adds three columns:
    - Calculated nM: Always computed from ng/µl and bp
    - Effective nM (Use): Empirical nM if available, else Calculated nM
    - Adjusted lib nM: Same as Effective nM (for compatibility)

    Args:
        df: DataFrame with normalized column names

    Returns:
        DataFrame with added molarity columns

    Raises:
        ValueError: If required columns missing or calculations fail
    """
    df = df.copy()

    # Validate required columns
    required = ["Final ng/ul", "Adjusted peak size"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Calculate molarity for all libraries
    calculated_nm = []
    for idx, row in df.iterrows():
        conc = row["Final ng/ul"]
        size = row["Adjusted peak size"]

        try:
            nm = compute_molarity_from_concentration(conc, size)
            calculated_nm.append(nm)
        except ValueError as e:
            raise ValueError(f"Row {idx + 1}: {e}")

    df["Calculated nM"] = calculated_nm

    # Determine effective molarity (empirical if available, else calculated)
    if "Empirical Library nM" in df.columns:
        df["Effective nM (Use)"] = df.apply(
            lambda row: row["Empirical Library nM"]
            if pd.notna(row["Empirical Library nM"]) and row["Empirical Library nM"] > 0
            else row["Calculated nM"],
            axis=1
        )
    else:
        df["Effective nM (Use)"] = df["Calculated nM"]

    # Adjusted lib nM is same as effective (no adapter dimer adjustment in current version)
    df["Adjusted lib nM"] = df["Effective nM (Use)"]

    return df


def compute_pool_volumes(
    df: pd.DataFrame,
    scaling_factor: float = 0.1,
    min_volume_ul: float = 0.001,
    max_volume_ul: float | None = None,
    total_reads_m: float | None = None
) -> pd.DataFrame:
    """
    Calculate volumes for each library to achieve weighted pooling.

    **CORRECTED FORMULA** (based on 7050I_miRNA_pool_copy.xlsx):
    1. Calculate stock volume: stock_vol = scaling_factor / adj_lib_nM * target_reads_M
    2. Determine pre-dilution factor:
       - If stock_vol < 0.2 µL: pre_dilute = 10x
       - If stock_vol < 0.795 µL: pre_dilute = 5x
       - Else: pre_dilute = 1x (no dilution)
    3. Calculate final volume: final_vol = stock_vol * pre_dilute_factor
    4. Check constraints and add flags
    5. Calculate derived metrics (pool fraction, expected reads)

    Args:
        df: DataFrame with effective molarity and target reads
        scaling_factor: Volume scaling factor (default 0.1, from Cell AA4 in reference)
        min_volume_ul: Minimum pipettable volume for flagging (default 0.001 µl)
        max_volume_ul: Maximum volume per library (optional)
        total_reads_m: Total sequencing reads in millions (optional, for reporting)

    Returns:
        DataFrame with added volume and metrics columns

    Raises:
        ValueError: If required columns missing or parameters invalid
    """
    df = df.copy()

    # Import thresholds from config
    from pooling_calculator.config import (
        PRE_DILUTE_THRESHOLD_10X,
        PRE_DILUTE_THRESHOLD_5X,
    )

    # Validate inputs
    if scaling_factor <= 0:
        raise ValueError(f"Scaling factor must be > 0, got {scaling_factor}")
    if min_volume_ul < 0:
        raise ValueError(f"Min volume must be >= 0, got {min_volume_ul}")
    if max_volume_ul is not None and max_volume_ul < 0:
        raise ValueError(f"Max volume must be >= 0, got {max_volume_ul}")

    # Validate required columns
    required = ["Adjusted lib nM", "Target Reads (M)"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Step 1: Calculate stock volume using CORRECT formula from spreadsheet
    # Formula: stock_vol = scaling_factor / adj_lib_nM * target_reads_M
    # This is from Cell AF in the reference spreadsheet: =$AA$4/R*Q
    df["Stock Volume (µl)"] = (scaling_factor / df["Adjusted lib nM"]) * df["Target Reads (M)"]

    # Step 2: Determine pre-dilution factor based on stock volume
    # Logic from Column Z in reference spreadsheet
    # IF stock_vol < 0.2: dilute 10x
    # ELIF stock_vol < 0.795: dilute 5x
    # ELSE: no dilution (1x)
    def calculate_pre_dilute_factor(stock_vol):
        """
        Calculate pre-dilution factor based on stock volume.

        Thresholds are configurable in config.py:
        - PRE_DILUTE_THRESHOLD_10X = 0.2 µL (default)
        - PRE_DILUTE_THRESHOLD_5X = 0.795 µL (default)
        """
        if stock_vol < PRE_DILUTE_THRESHOLD_10X:
            return 10
        elif stock_vol < PRE_DILUTE_THRESHOLD_5X:
            return 5
        else:
            return 1

    df["Pre-Dilute Factor"] = df["Stock Volume (µl)"].apply(calculate_pre_dilute_factor)

    # Step 3: Calculate final volume (volume to actually pipette)
    # Formula from Column AA: vol = stock_vol * pre_dilute_factor
    df["Final Volume (µl)"] = df["Stock Volume (µl)"] * df["Pre-Dilute Factor"]

    # Initialize flags column
    df["Flags"] = ""

    # Step 4: Validation checks and flag problematic libraries
    for idx, row in df.iterrows():
        flags = []
        stock_vol = row["Stock Volume (µl)"]
        final_vol = row["Final Volume (µl)"]
        pre_dilute = row["Pre-Dilute Factor"]

        # Check against total available volume
        if "Total Volume" in df.columns:
            available = row["Total Volume"]
            if final_vol > available:
                flags.append(f"Insufficient volume (need {final_vol:.3f} µl, have {available:.3f} µl)")

        # Informational flag for pre-dilution
        if pre_dilute > 1:
            flags.append(f"Pre-dilute {pre_dilute}x recommended (stock vol {stock_vol:.3f} µl)")

        # Check minimum pipettable volume (should be rare with pre-dilution)
        if final_vol < min_volume_ul:
            flags.append(f"Below minimum pipettable volume ({final_vol:.6f} µl < {min_volume_ul} µl)")

        # Check maximum volume constraint
        if max_volume_ul is not None and final_vol > max_volume_ul:
            flags.append(f"Exceeds maximum volume ({final_vol:.3f} µl > {max_volume_ul} µl)")

        df.at[idx, "Flags"] = "; ".join(flags)

    # Step 5: Calculate pool fraction: f[i] = (V[i] * C[i]) / sum(V[j] * C[j])
    # Use stock volume (before dilution) for pool fraction calculation
    df["_mol_contribution"] = df["Stock Volume (µl)"] * df["Adjusted lib nM"]
    total_mol = df["_mol_contribution"].sum()
    df["Pool Fraction"] = df["_mol_contribution"] / total_mol

    # Calculate expected reads if total reads provided
    if total_reads_m is not None:
        df["Expected Reads (M)"] = df["Pool Fraction"] * total_reads_m

    # Clean up temporary columns
    df = df.drop(columns=["_mol_contribution"])

    return df


def summarize_by_project(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate library-level results by project.

    Args:
        df: DataFrame with computed volumes and metrics

    Returns:
        DataFrame with project-level summary

    Raises:
        ValueError: If required columns missing
    """
    # Validate required columns
    if "Project ID" not in df.columns:
        raise ValueError("Missing required column: Project ID")

    # Group by project
    grouped = df.groupby("Project ID")

    # Aggregate metrics
    summary = pd.DataFrame({
        "Project ID": grouped["Project ID"].first(),
        "Number of Libraries": grouped.size(),
        "Total Volume (µl)": grouped["Stock Volume (µl)"].sum() if "Stock Volume (µl)" in df.columns else 0,
        "Pool Fraction": grouped["Pool Fraction"].sum() if "Pool Fraction" in df.columns else 0,
    })

    # Add expected reads if available
    if "Expected Reads (M)" in df.columns:
        summary["Expected Reads (M)"] = grouped["Expected Reads (M)"].sum()

    # Reset index for clean output
    summary = summary.reset_index(drop=True)

    return summary
