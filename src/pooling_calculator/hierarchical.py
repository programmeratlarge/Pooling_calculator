"""
Hierarchical pooling functions for multi-step pooling workflows.

This module implements functions for hierarchical pooling, where libraries are pooled
in multiple stages: libraries → sub-pools → master pool. This is essential for
ultra-high-plex experiments where pipetting hundreds of individual libraries
into a single pool is impractical.
"""

import pandas as pd
from datetime import datetime

from pooling_calculator.models import (
    SubPoolRecord,
    PoolingStage,
    PoolingStageData,
    HierarchicalPoolingPlan,
)
from pooling_calculator.compute import compute_pool_volumes
from pooling_calculator.config import (
    PRE_DILUTE_THRESHOLD_10X,
    PRE_DILUTE_THRESHOLD_5X,
    MAX_LIBRARIES_PER_POOL,
    MIN_SUBPOOLS_FOR_HIERARCHICAL,
    HIERARCHICAL_GROUPING_COLUMNS,
    DEFAULT_MAX_LIBRARIES_PER_SUBPOOL,
)


# ============================================================================
# Strategy Selection
# ============================================================================


def determine_pooling_strategy(
    df: pd.DataFrame,
    max_libraries_per_pool: int = MAX_LIBRARIES_PER_POOL,
    min_subpools_for_hierarchical: int = MIN_SUBPOOLS_FOR_HIERARCHICAL,
) -> tuple[str, list[str], dict[str, any]]:
    """
    Decide if hierarchical pooling is needed based on library count and grouping.

    This function analyzes the input DataFrame to recommend the optimal pooling
    strategy (single-stage vs. hierarchical) and suggests grouping columns.

    Args:
        df: DataFrame with library data (must include columns for analysis)
        max_libraries_per_pool: Maximum libraries per single pool (default: 96)
        min_subpools_for_hierarchical: Minimum sub-pools to justify hierarchical (default: 5)

    Returns:
        Tuple of (strategy, grouping_options, analysis):
        - strategy: "single_stage" or "hierarchical"
        - grouping_options: List of suggested column names for sub-pool grouping
        - analysis: Dict with analysis details (total_libraries, num_projects, etc.)

    Logic:
        1. If total libraries <= max_libraries_per_pool → "single_stage"
        2. Check each potential grouping column (e.g., "Project ID"):
           - Count unique groups
           - If groups >= min_subpools_for_hierarchical → "hierarchical"
        3. Return best strategy and recommended grouping column(s)

    Example:
        >>> df = pd.DataFrame({"Project ID": ["A"]*50 + ["B"]*60, ...})
        >>> strategy, columns, analysis = determine_pooling_strategy(df)
        >>> strategy
        'hierarchical'
        >>> columns
        ['Project ID']
        >>> analysis
        {'total_libraries': 110, 'num_projects': 2, 'recommended': True}
    """
    total_libraries = len(df)

    # Analysis results
    analysis = {
        "total_libraries": total_libraries,
        "max_libraries_per_pool": max_libraries_per_pool,
    }

    # Strategy 1: Small experiment → single-stage
    if total_libraries <= max_libraries_per_pool:
        analysis["reason"] = "Small experiment (<=96 libraries)"
        analysis["recommended"] = False
        return "single_stage", [], analysis

    # Strategy 2: Analyze potential grouping columns
    grouping_options = []

    for col in HIERARCHICAL_GROUPING_COLUMNS:
        if col not in df.columns:
            continue

        # Count unique groups
        unique_groups = df[col].nunique()
        analysis[f"{col}_num_groups"] = unique_groups

        # Check if this column creates enough sub-pools
        if unique_groups >= min_subpools_for_hierarchical:
            grouping_options.append(col)
            analysis[f"{col}_viable"] = True
        else:
            analysis[f"{col}_viable"] = False

    # Decision logic
    if len(grouping_options) > 0:
        # Hierarchical pooling is viable and recommended
        analysis["reason"] = (
            f"Large experiment ({total_libraries} libraries) with natural grouping"
        )
        analysis["recommended"] = True
        return "hierarchical", grouping_options, analysis
    else:
        # Large experiment but no good grouping column
        # Still recommend hierarchical with custom/manual grouping
        analysis["reason"] = (
            f"Large experiment ({total_libraries} libraries) requires hierarchical approach"
        )
        analysis["recommended"] = True
        analysis["warning"] = (
            "No natural grouping column found. Consider adding 'Project ID' or use custom grouping."
        )
        return "hierarchical", [], analysis


# ============================================================================
# Sub-Pool Definition Functions
# ============================================================================


def create_subpool_definitions(
    df: pd.DataFrame,
    grouping_column: str = "Project ID",
    max_libraries_per_subpool: int = 96,
) -> pd.DataFrame:
    """
    Define sub-pools based on grouping criteria.

    This function adds a "SubPool ID" column to the DataFrame, grouping libraries
    based on the specified column. Large groups are automatically split to respect
    the max_libraries_per_subpool constraint.

    Args:
        df: DataFrame with library data (must include grouping_column)
        grouping_column: Column to group by (default: "Project ID")
        max_libraries_per_subpool: Maximum libraries per sub-pool (default: 96 for plate layout)

    Returns:
        DataFrame with additional "SubPool ID" column

    Raises:
        ValueError: If grouping_column is not in DataFrame

    Example:
        Input: 150 libraries with Project ID = "ProjectA"
        Output: Same libraries split into "ProjectA_pool_1" and "ProjectA_pool_2"
    """
    if grouping_column not in df.columns:
        raise ValueError(f"Grouping column '{grouping_column}' not found in DataFrame")

    df = df.copy()
    subpool_ids = []

    for group_name, group_df in df.groupby(grouping_column):
        group_size = len(group_df)

        if group_size <= max_libraries_per_subpool:
            # Single sub-pool for this group
            subpool_ids.extend([f"{group_name}_pool"] * group_size)
        else:
            # Split into multiple sub-pools
            num_subpools = (group_size + max_libraries_per_subpool - 1) // max_libraries_per_subpool

            for i, (_, subgroup_df) in enumerate(
                group_df.groupby(group_df.index // max_libraries_per_subpool), start=1
            ):
                subpool_id = f"{group_name}_pool_{i}"
                subpool_ids.extend([subpool_id] * len(subgroup_df))

    df["SubPool ID"] = subpool_ids
    return df


def compute_subpool_properties(
    df_libraries: pd.DataFrame,
    df_volumes: pd.DataFrame,
    subpool_id: str,
) -> SubPoolRecord:
    """
    Calculate properties of a sub-pool after pooling its member libraries.

    This function computes the effective molarity and total volume of a sub-pool
    based on the pooling volumes of its member libraries.

    Args:
        df_libraries: Original library data (with "Adjusted lib nM" column)
        df_volumes: Pooling volumes for libraries in this sub-pool
        subpool_id: Identifier for this sub-pool

    Returns:
        SubPoolRecord with calculated molarity and total volume

    Logic:
        1. Sum volumes: V_total = Σ V_i
        2. Calculate total moles: n_total = Σ (C_i × V_i)
        3. Calculate sub-pool molarity: C_subpool = n_total / V_total
        4. Sum target reads: TR_subpool = Σ TR_i

    Raises:
        ValueError: If required columns are missing or data is inconsistent
    """
    # Validate required columns
    required_lib_cols = ["Library Name", "Adjusted lib nM", "Target Reads (M)"]
    missing_lib_cols = [col for col in required_lib_cols if col not in df_libraries.columns]
    if missing_lib_cols:
        raise ValueError(f"Missing required library columns: {missing_lib_cols}")

    required_vol_cols = ["Library Name", "Final Volume (µl)"]
    missing_vol_cols = [col for col in required_vol_cols if col not in df_volumes.columns]
    if missing_vol_cols:
        raise ValueError(f"Missing required volume columns: {missing_vol_cols}")

    # Merge library data with volumes
    merged = df_libraries.merge(df_volumes[["Library Name", "Final Volume (µl)"]], on="Library Name")

    # Calculate sub-pool properties
    # Step 1: Total volume
    total_volume_ul = merged["Final Volume (µl)"].sum()

    # Step 2: Total moles (nM × µL gives nanomoles)
    merged["nanomoles"] = merged["Adjusted lib nM"] * merged["Final Volume (µl)"]
    total_nanomoles = merged["nanomoles"].sum()

    # Step 3: Sub-pool molarity
    calculated_nm = total_nanomoles / total_volume_ul if total_volume_ul > 0 else 0.0

    # Step 4: Sum target reads
    target_reads_m = merged["Target Reads (M)"].sum()

    # Get member library names
    member_libraries = merged["Library Name"].tolist()

    # Extract project ID if available
    parent_project_id = None
    if "Project ID" in df_libraries.columns and len(merged) > 0:
        # Use the project ID from the first library (should be same for all in sub-pool)
        parent_project_id = merged["Project ID"].iloc[0]

    return SubPoolRecord(
        subpool_id=subpool_id,
        member_libraries=member_libraries,
        calculated_nm=calculated_nm,
        total_volume_ul=total_volume_ul,
        target_reads_m=target_reads_m,
        creation_date=datetime.now(),
        parent_project_id=parent_project_id,
        custom_grouping=None,
    )


# ============================================================================
# Hierarchical Pooling Workflow
# ============================================================================


def compute_hierarchical_pooling(
    df: pd.DataFrame,
    grouping_column: str = "Project ID",
    scaling_factor: float = 0.1,
    final_pool_volume_ul: float = 20.0,
    min_volume_ul: float = 0.001,
    max_volume_ul: float | None = None,
    total_reads_m: float | None = None,
) -> HierarchicalPoolingPlan:
    """
    Complete hierarchical pooling workflow.

    This function implements a two-stage pooling strategy:
    1. Pool libraries into sub-pools (grouped by grouping_column)
    2. Pool sub-pools into a master pool

    Args:
        df: Library data with all required columns
        grouping_column: How to group libraries into sub-pools (default: "Project ID")
        scaling_factor: Scaling factor for volume calculation (default: 0.1)
        final_pool_volume_ul: Target volume for master pool (default: 20.0)
        min_volume_ul: Minimum pipettable volume (default: 0.001)
        max_volume_ul: Maximum volume per pipetting step (default: None)
        total_reads_m: Total sequencing reads in millions (default: None)

    Returns:
        HierarchicalPoolingPlan with complete multi-stage workflow

    Workflow:
        Stage 1: Libraries → Sub-pools
            - Group libraries by grouping_column
            - For each group, compute pooling volumes
            - Create SubPoolRecord for each sub-pool

        Stage 2: Sub-pools → Master Pool
            - Treat SubPoolRecords as "super-libraries"
            - Apply same pooling algorithm to combine sub-pools

    Raises:
        ValueError: If required columns are missing or data is invalid
    """
    # Validate required columns
    required_cols = ["Library Name", "Adjusted lib nM", "Target Reads (M)"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    if grouping_column not in df.columns:
        raise ValueError(f"Grouping column '{grouping_column}' not found in DataFrame")

    # ========== STAGE 1: Libraries → Sub-pools ==========

    # Create sub-pool definitions
    df_with_subpools = create_subpool_definitions(df, grouping_column=grouping_column)

    # Compute volumes for each sub-pool
    subpool_records = []
    stage1_volumes_list = []

    for subpool_id in df_with_subpools["SubPool ID"].unique():
        # Get libraries for this sub-pool
        subpool_df = df_with_subpools[df_with_subpools["SubPool ID"] == subpool_id].copy()

        # Compute pooling volumes for this sub-pool
        subpool_volumes = compute_pool_volumes(
            subpool_df,
            scaling_factor=scaling_factor,
            min_volume_ul=min_volume_ul,
            max_volume_ul=max_volume_ul,
            total_reads_m=None,  # Don't calculate expected reads at this stage
        )

        # Store volumes with SubPool ID for tracking
        subpool_volumes["SubPool ID"] = subpool_id
        stage1_volumes_list.append(subpool_volumes)

        # Compute sub-pool properties
        subpool_record = compute_subpool_properties(subpool_df, subpool_volumes, subpool_id)
        subpool_records.append(subpool_record)

    # Combine all stage 1 volumes
    df_stage1_volumes = pd.concat(stage1_volumes_list, ignore_index=True)

    # Create Stage 1 data
    stage1 = PoolingStageData(
        stage=PoolingStage.LIBRARY_TO_SUBPOOL,
        stage_number=1,
        input_count=len(df),
        output_count=len(subpool_records),
        volumes_df_json=df_stage1_volumes.to_dict(orient="records"),
        total_pipetting_steps=len(df),
        description=f"Pool {len(df)} libraries into {len(subpool_records)} sub-pools by {grouping_column}",
        warnings=[],
    )

    # ========== STAGE 2: Sub-pools → Master Pool ==========

    # Create DataFrame from sub-pool records (treating them as "super-libraries")
    subpool_data = []
    for sp in subpool_records:
        subpool_data.append(
            {
                "Library Name": sp.subpool_id,
                "Adjusted lib nM": sp.calculated_nm,
                "Target Reads (M)": sp.target_reads_m,
                "Total Volume": sp.total_volume_ul,
                "Project ID": sp.parent_project_id if sp.parent_project_id else "SubPool",
            }
        )

    df_subpools = pd.DataFrame(subpool_data)

    # Compute volumes for combining sub-pools into master pool
    df_stage2_volumes = compute_pool_volumes(
        df_subpools,
        scaling_factor=scaling_factor,
        min_volume_ul=min_volume_ul,
        max_volume_ul=max_volume_ul,
        total_reads_m=total_reads_m,
    )

    # Create Stage 2 data
    stage2 = PoolingStageData(
        stage=PoolingStage.SUBPOOL_TO_MASTER,
        stage_number=2,
        input_count=len(subpool_records),
        output_count=1,
        volumes_df_json=df_stage2_volumes.to_dict(orient="records"),
        total_pipetting_steps=len(subpool_records),
        description=f"Pool {len(subpool_records)} sub-pools into 1 master pool",
        warnings=[],
    )

    # ========== Create Hierarchical Pooling Plan ==========

    total_pipetting_steps = stage1.total_pipetting_steps + stage2.total_pipetting_steps

    plan = HierarchicalPoolingPlan(
        stages=[stage1, stage2],
        final_pool_volume_ul=final_pool_volume_ul,
        total_libraries=len(df),
        total_subpools=len(subpool_records),
        strategy="hierarchical",
        grouping_method=grouping_column,
        created_at=datetime.now(),
        parameters={
            "scaling_factor": scaling_factor,
            "min_volume_ul": min_volume_ul,
            "max_volume_ul": max_volume_ul,
            "total_reads_m": total_reads_m,
        },
        total_pipetting_steps=total_pipetting_steps,
        estimated_time_minutes=None,  # Could be calculated based on pipetting time estimates
    )

    return plan
