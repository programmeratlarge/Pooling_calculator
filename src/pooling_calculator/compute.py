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
    desired_pool_volume_ul: float,
    min_volume_ul: float = 0.001,
    max_volume_ul: float | None = None,
    total_reads_m: float | None = None
) -> pd.DataFrame:
    """
    Calculate volumes for each library to achieve weighted pooling.

    Algorithm:
    1. For each library i: v_raw[i] = target_reads[i] / molarity[i]
    2. Scale to desired pool volume: V[i] = v_raw[i] × (desired_volume / sum(v_raw))
    3. Check constraints and add flags
    4. Calculate derived metrics (pool fraction, expected reads)

    Args:
        df: DataFrame with effective molarity and target reads
        desired_pool_volume_ul: Target total volume for final pool
        min_volume_ul: Minimum pipettable volume (default 0.001 µl = 1 nL)
        max_volume_ul: Maximum volume per library (optional)
        total_reads_m: Total sequencing reads in millions (optional, for reporting)

    Returns:
        DataFrame with added volume and metrics columns

    Raises:
        ValueError: If required columns missing or parameters invalid
    """
    df = df.copy()

    # Validate inputs
    if desired_pool_volume_ul <= 0:
        raise ValueError(f"Desired pool volume must be > 0, got {desired_pool_volume_ul}")
    if min_volume_ul < 0:
        raise ValueError(f"Min volume must be >= 0, got {min_volume_ul}")
    if max_volume_ul is not None and max_volume_ul <= 0:
        raise ValueError(f"Max volume must be > 0, got {max_volume_ul}")

    # Validate required columns
    required = ["Effective nM (Use)", "Target Reads (M)"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Calculate raw volume factors: v_raw[i] = target_reads[i] / molarity[i]
    df["_v_raw"] = df["Target Reads (M)"] / df["Effective nM (Use)"]

    # Calculate scaling factor to achieve desired pool volume
    v_raw_total = df["_v_raw"].sum()
    scale_factor = desired_pool_volume_ul / v_raw_total

    # Calculate final volumes
    df["Stock Volume (µl)"] = df["_v_raw"] * scale_factor

    # Initialize flags column
    df["Flags"] = ""

    # Sanity checks
    for idx, row in df.iterrows():
        flags = []
        volume = row["Stock Volume (µl)"]

        # Check against total available volume
        if "Total Volume" in df.columns:
            available = row["Total Volume"]
            if volume > available:
                flags.append(f"Insufficient volume (need {volume:.3f} µl, have {available:.3f} µl)")

        # Check minimum pipettable volume
        if volume < min_volume_ul:
            flags.append(f"Below minimum pipettable volume ({volume:.6f} µl < {min_volume_ul} µl)")

        # Check maximum volume constraint
        if max_volume_ul is not None and volume > max_volume_ul:
            flags.append(f"Exceeds maximum volume ({volume:.3f} µl > {max_volume_ul} µl)")

        df.at[idx, "Flags"] = "; ".join(flags)

    # Calculate pool fraction: f[i] = (V[i] * C[i]) / sum(V[j] * C[j])
    df["_mol_contribution"] = df["Stock Volume (µl)"] * df["Effective nM (Use)"]
    total_mol = df["_mol_contribution"].sum()
    df["Pool Fraction"] = df["_mol_contribution"] / total_mol

    # Calculate expected reads if total reads provided
    if total_reads_m is not None:
        df["Expected Reads (M)"] = df["Pool Fraction"] * total_reads_m

    # Clean up temporary columns
    df = df.drop(columns=["_v_raw", "_mol_contribution"])

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
