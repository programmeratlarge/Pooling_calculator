"""
Pre-pooling functions for user-defined library grouping.

This module implements the pre-pooling workflow where users manually select
specific libraries to pool together before the final pooling step. This is
analogous to the "Prepool 1", "Prepool 2" functionality in the reference
Excel spreadsheet.

Workflow:
1. User selects libraries for each pre-pool
2. Calculate volumes for libraries within each pre-pool
3. Compute pre-pool properties (concentration, volume)
4. Treat pre-pools as "super-libraries" with remaining individual libraries
5. Calculate final pool with both pre-pools and standalone libraries
"""

import pandas as pd
from datetime import datetime
from typing import Any

from pooling_calculator.models import (
    PrePoolDefinition,
    PrePoolCalculationResult,
    PrePoolingPlan,
)
from pooling_calculator.compute import compute_pool_volumes


# ============================================================================
# Pre-Pool Creation Functions
# ============================================================================


def create_prepool_from_selection(
    df: pd.DataFrame,
    selected_library_names: list[str],
    prepool_name: str,
    scaling_factor: float,
    min_volume_ul: float,
    max_volume_ul: float | None,
) -> PrePoolCalculationResult:
    """
    Calculate pooling volumes for a user-defined pre-pool.

    Args:
        df: Full library DataFrame with molarity (must include "Adjusted lib nM",
            "Target Reads (M)", "Library Name" columns)
        selected_library_names: Libraries to include in this pre-pool
        prepool_name: Display name for this pre-pool
        scaling_factor: Volume calculation parameter
        min_volume_ul: Minimum pipettable volume
        max_volume_ul: Maximum volume constraint (optional)

    Returns:
        PrePoolCalculationResult with volumes and calculated properties

    Raises:
        ValueError: If selected libraries not found in DataFrame
        ValueError: If DataFrame missing required columns

    Logic:
        1. Filter df to selected libraries
        2. Run compute_pool_volumes() on this subset
        3. Calculate pre-pool properties:
           - Total volume = sum of member volumes
           - Total moles = sum(C_i × V_i)
           - Effective concentration = total moles / total volume
           - Target reads = sum of member target reads
        4. Return wrapped result
    """
    # Validate required columns
    required_cols = ["Library Name", "Adjusted lib nM", "Target Reads (M)"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Filter to selected libraries
    selected_df = df[df["Library Name"].isin(selected_library_names)].copy()

    if len(selected_df) == 0:
        raise ValueError(f"No libraries found matching selection: {selected_library_names}")

    if len(selected_df) != len(selected_library_names):
        found = set(selected_df["Library Name"])
        requested = set(selected_library_names)
        missing = requested - found
        raise ValueError(f"Some selected libraries not found: {missing}")

    # Calculate pooling volumes for this pre-pool
    prepool_volumes_df = compute_pool_volumes(
        selected_df,
        scaling_factor=scaling_factor,
        min_volume_ul=min_volume_ul,
        max_volume_ul=max_volume_ul,
        total_reads_m=None,  # Don't calculate expected reads within pre-pool
    )

    # Calculate pre-pool properties
    # Step 1: Total volume (sum of all member volumes)
    total_volume_ul = prepool_volumes_df["Final Volume (µl)"].sum()

    # Step 2: Calculate prepool concentration using reference spreadsheet method
    # Per user feedback from 7050I_miRNA_pool_copy.xlsx:
    # - adj lib pmol = Target Reads (M) / 10 (desired relative picomole contribution)
    # - Prepool nM = sum(adj lib pmol) / sum(pool volumes)
    # This ensures the prepool concentration reflects the weighted target reads
    prepool_volumes_df["adj lib pmol"] = prepool_volumes_df["Target Reads (M)"] / 10.0
    total_pmol = prepool_volumes_df["adj lib pmol"].sum()

    # Step 3: Pre-pool effective concentration
    calculated_nm = total_pmol / total_volume_ul if total_volume_ul > 0 else 0.0

    # Step 4: Sum target reads from all members
    target_reads_m = prepool_volumes_df["Target Reads (M)"].sum()

    # Create PrePoolDefinition
    prepool_def = PrePoolDefinition(
        prepool_id=prepool_name.lower().replace(" ", "_"),
        prepool_name=prepool_name,
        member_library_names=selected_library_names,
        created_at=datetime.now(),
        notes=None,
    )

    # Return result
    return PrePoolCalculationResult(
        prepool_definition=prepool_def,
        calculated_nm=calculated_nm,
        total_volume_ul=total_volume_ul,
        target_reads_m=target_reads_m,
        member_volumes_json=prepool_volumes_df.to_dict(orient="records"),
    )


# ============================================================================
# Pre-Pooling Workflow
# ============================================================================


def compute_with_prepools(
    df: pd.DataFrame,
    prepool_definitions: list[PrePoolDefinition],
    scaling_factor: float,
    min_volume_ul: float,
    max_volume_ul: float | None,
    total_reads_m: float | None,
) -> PrePoolingPlan:
    """
    Complete pre-pooling workflow.

    Args:
        df: Full library DataFrame with molarity
        prepool_definitions: List of user-defined pre-pools
        scaling_factor: Volume calculation parameter
        min_volume_ul: Minimum pipettable volume
        max_volume_ul: Maximum volume constraint
        total_reads_m: Total sequencing reads (for final pool calculation)

    Returns:
        PrePoolingPlan with all results

    Raises:
        ValueError: If libraries appear in multiple pre-pools
        ValueError: If required columns missing

    Workflow:
        1. Validate that libraries don't appear in multiple pre-pools
        2. For each prepool_definition:
           - Calculate volumes for member libraries
           - Compute pre-pool properties (concentration, total volume)
        3. Identify remaining libraries (not in any pre-pool)
        4. Create "super-libraries" DataFrame:
           - Each pre-pool becomes a row with:
             * Library Name = prepool_id
             * Adjusted lib nM = calculated_nm
             * Target Reads (M) = sum of member target reads
             * Total Volume = pre-pool total volume
        5. Combine remaining libraries + pre-pools
        6. Run compute_pool_volumes() on combined DataFrame
        7. Return complete plan

    Example:
        >>> prepools = [
        ...     PrePoolDefinition(
        ...         prepool_id="prepool_1",
        ...         prepool_name="Prepool 1",
        ...         member_library_names=["Lib001", "Lib002"],
        ...         created_at=datetime.now()
        ...     )
        ... ]
        >>> plan = compute_with_prepools(df, prepools, 0.1, 0.5, None, 100.0)
    """
    # Validate inputs
    if not prepool_definitions:
        raise ValueError("At least one pre-pool definition required")

    required_cols = ["Library Name", "Adjusted lib nM", "Target Reads (M)", "Total Volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Step 1: Validate no overlapping libraries
    all_prepool_libraries = []
    for prepool_def in prepool_definitions:
        all_prepool_libraries.extend(prepool_def.member_library_names)

    if len(all_prepool_libraries) != len(set(all_prepool_libraries)):
        # Find duplicates
        from collections import Counter
        counts = Counter(all_prepool_libraries)
        duplicates = [lib for lib, count in counts.items() if count > 1]
        raise ValueError(f"Libraries appear in multiple pre-pools: {duplicates}")

    # Step 2: Calculate each pre-pool
    prepool_results = []
    for prepool_def in prepool_definitions:
        result = create_prepool_from_selection(
            df=df,
            selected_library_names=prepool_def.member_library_names,
            prepool_name=prepool_def.prepool_name,
            scaling_factor=scaling_factor,
            min_volume_ul=min_volume_ul,
            max_volume_ul=max_volume_ul,
        )
        prepool_results.append(result)

    # Step 3: Identify remaining libraries (not in any pre-pool)
    libraries_in_prepools = set(all_prepool_libraries)
    all_libraries = set(df["Library Name"])
    remaining_library_names = all_libraries - libraries_in_prepools

    remaining_df = df[df["Library Name"].isin(remaining_library_names)].copy()

    # Step 4: Create "super-libraries" from pre-pools
    prepool_rows = []
    for result in prepool_results:
        prepool_rows.append({
            "Library Name": result.prepool_definition.prepool_id,
            "Adjusted lib nM": result.calculated_nm,
            "Target Reads (M)": result.target_reads_m,
            "Total Volume": result.total_volume_ul,
            "Project ID": "PrePool",  # Mark as pre-pool
        })

    df_prepools = pd.DataFrame(prepool_rows)

    # Step 5: Combine remaining libraries + pre-pools
    if len(remaining_df) > 0:
        # Ensure both have same columns for concat
        common_cols = ["Library Name", "Adjusted lib nM", "Target Reads (M)", "Total Volume", "Project ID"]
        remaining_subset = remaining_df[common_cols].copy()
        combined_df = pd.concat([remaining_subset, df_prepools], ignore_index=True)
    else:
        combined_df = df_prepools

    # Step 6: Calculate final pool
    final_pool_df = compute_pool_volumes(
        combined_df,
        scaling_factor=scaling_factor,
        min_volume_ul=min_volume_ul,
        max_volume_ul=max_volume_ul,
        total_reads_m=total_reads_m,
    )

    # Step 7: Build PrePoolingPlan
    return PrePoolingPlan(
        prepools=prepool_results,
        remaining_libraries_json=remaining_df.to_dict(orient="records") if len(remaining_df) > 0 else [],
        final_pool_json=final_pool_df.to_dict(orient="records"),
        total_libraries=len(df),
        libraries_in_prepools=len(libraries_in_prepools),
        standalone_libraries=len(remaining_library_names),
        created_at=datetime.now(),
        parameters={
            "scaling_factor": scaling_factor,
            "min_volume_ul": min_volume_ul,
            "max_volume_ul": max_volume_ul,
            "total_reads_m": total_reads_m,
        },
    )


# ============================================================================
# Validation Functions
# ============================================================================


def validate_prepool_definitions(
    df: pd.DataFrame,
    prepool_definitions: list[PrePoolDefinition],
) -> tuple[bool, list[str]]:
    """
    Validate pre-pool definitions against the library DataFrame.

    Args:
        df: Library DataFrame
        prepool_definitions: List of pre-pool definitions to validate

    Returns:
        Tuple of (is_valid, error_messages)

    Checks:
        1. All referenced libraries exist in DataFrame
        2. No library appears in multiple pre-pools
        3. Each pre-pool has at least one library
        4. Pre-pool IDs are unique
    """
    errors = []

    if not prepool_definitions:
        return True, []

    # Check 1: All libraries exist
    all_libraries = set(df["Library Name"])
    for prepool_def in prepool_definitions:
        for lib_name in prepool_def.member_library_names:
            if lib_name not in all_libraries:
                errors.append(
                    f"Library '{lib_name}' in pre-pool '{prepool_def.prepool_name}' "
                    f"not found in data"
                )

    # Check 2: No overlapping libraries
    all_prepool_libs = []
    for prepool_def in prepool_definitions:
        all_prepool_libs.extend(prepool_def.member_library_names)

    if len(all_prepool_libs) != len(set(all_prepool_libs)):
        from collections import Counter
        counts = Counter(all_prepool_libs)
        duplicates = [lib for lib, count in counts.items() if count > 1]
        errors.append(f"Libraries appear in multiple pre-pools: {', '.join(duplicates)}")

    # Check 3: Each pre-pool has libraries
    for prepool_def in prepool_definitions:
        if len(prepool_def.member_library_names) == 0:
            errors.append(f"Pre-pool '{prepool_def.prepool_name}' has no libraries")

    # Check 4: Unique pre-pool IDs
    prepool_ids = [p.prepool_id for p in prepool_definitions]
    if len(prepool_ids) != len(set(prepool_ids)):
        from collections import Counter
        counts = Counter(prepool_ids)
        duplicates = [pid for pid, count in counts.items() if count > 1]
        errors.append(f"Duplicate pre-pool IDs: {', '.join(duplicates)}")

    return len(errors) == 0, errors
