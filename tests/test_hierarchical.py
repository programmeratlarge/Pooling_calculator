"""
Unit tests for hierarchical pooling functions.

Tests the multi-stage pooling workflow: libraries → sub-pools → master pool.
"""

import pytest
import pandas as pd
from datetime import datetime

from pooling_calculator.hierarchical import (
    determine_pooling_strategy,
    create_subpool_definitions,
    compute_subpool_properties,
    compute_hierarchical_pooling,
)
from pooling_calculator.models import (
    SubPoolRecord,
    HierarchicalPoolingPlan,
    PoolingStage,
)


# ============================================================================
# Test determine_pooling_strategy
# ============================================================================


def test_determine_pooling_strategy_small_experiment():
    """Test that small experiments recommend single-stage."""
    # Create 50 libraries (< 96)
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 30 + ["ProjB"] * 20,
        "Library Name": [f"Lib{i:03d}" for i in range(50)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    assert strategy == "single_stage"
    assert len(grouping_options) == 0
    assert analysis["total_libraries"] == 50
    assert analysis["recommended"] == False
    assert "Small experiment" in analysis["reason"]


def test_determine_pooling_strategy_large_with_good_grouping():
    """Test that large experiments with good grouping recommend hierarchical."""
    # Create 200 libraries across 8 projects
    df = pd.DataFrame({
        "Project ID": [f"Proj{chr(65+i//25)}" for i in range(200)],
        "Library Name": [f"Lib{i:03d}" for i in range(200)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    assert strategy == "hierarchical"
    assert "Project ID" in grouping_options
    assert analysis["total_libraries"] == 200
    assert analysis["recommended"] == True
    assert analysis["Project ID_num_groups"] == 8
    assert analysis["Project ID_viable"] == True


def test_determine_pooling_strategy_large_no_grouping_column():
    """Test large experiment without grouping column still recommends hierarchical."""
    # Create 150 libraries without "Project ID" column
    df = pd.DataFrame({
        "Library Name": [f"Lib{i:03d}" for i in range(150)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    assert strategy == "hierarchical"
    assert len(grouping_options) == 0  # No viable grouping columns
    assert analysis["total_libraries"] == 150
    assert analysis["recommended"] == True
    assert "warning" in analysis
    assert "No natural grouping column" in analysis["warning"]


def test_determine_pooling_strategy_large_insufficient_groups():
    """Test large experiment with too few groups."""
    # Create 150 libraries across only 3 projects (< 5 threshold)
    df = pd.DataFrame({
        "Project ID": [f"Proj{chr(65+i//50)}" for i in range(150)],
        "Library Name": [f"Lib{i:03d}" for i in range(150)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    assert strategy == "hierarchical"  # Still recommend hierarchical for large experiments
    assert len(grouping_options) == 0  # But Project ID not viable (only 3 groups)
    assert analysis["total_libraries"] == 150
    assert analysis["recommended"] == True
    assert analysis["Project ID_num_groups"] == 3
    assert analysis["Project ID_viable"] == False


def test_determine_pooling_strategy_exactly_at_threshold():
    """Test experiment exactly at 96 libraries (edge case)."""
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 96,
        "Library Name": [f"Lib{i:03d}" for i in range(96)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    # Exactly 96 should be single-stage (not over threshold)
    assert strategy == "single_stage"
    assert len(grouping_options) == 0
    assert analysis["total_libraries"] == 96


def test_determine_pooling_strategy_just_over_threshold():
    """Test experiment just over 96 libraries."""
    # Create 97 libraries across 5 projects
    df = pd.DataFrame({
        "Project ID": [f"Proj{chr(65+i//20)}" for i in range(97)],
        "Library Name": [f"Lib{i:03d}" for i in range(97)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    # Just over 96 should recommend hierarchical
    assert strategy == "hierarchical"
    assert "Project ID" in grouping_options
    assert analysis["total_libraries"] == 97
    assert analysis["recommended"] == True


def test_determine_pooling_strategy_custom_thresholds():
    """Test with custom max_libraries_per_pool threshold."""
    # Create 60 libraries (normally single-stage)
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 60,
        "Library Name": [f"Lib{i:03d}" for i in range(60)],
    })

    # With custom threshold of 48, should recommend hierarchical
    strategy, grouping_options, analysis = determine_pooling_strategy(
        df,
        max_libraries_per_pool=48,
        min_subpools_for_hierarchical=1  # Lower threshold for testing
    )

    assert strategy == "hierarchical"
    assert analysis["max_libraries_per_pool"] == 48


def test_determine_pooling_strategy_analysis_details():
    """Test that analysis dict contains expected details."""
    df = pd.DataFrame({
        "Project ID": [f"Proj{chr(65+i//50)}" for i in range(200)],
        "Library Name": [f"Lib{i:03d}" for i in range(200)],
    })

    strategy, grouping_options, analysis = determine_pooling_strategy(df)

    # Check that analysis dict has expected keys
    assert "total_libraries" in analysis
    assert "max_libraries_per_pool" in analysis
    assert "reason" in analysis
    assert "recommended" in analysis
    assert "Project ID_num_groups" in analysis
    assert "Project ID_viable" in analysis


# ============================================================================
# Test create_subpool_definitions
# ============================================================================


def test_create_subpool_definitions_single_group():
    """Test sub-pool creation with single small group."""
    df = pd.DataFrame({
        "Project ID": ["ProjectA", "ProjectA", "ProjectA"],
        "Library Name": ["Lib1", "Lib2", "Lib3"],
        "Adjusted lib nM": [10.0, 20.0, 30.0],
        "Target Reads (M)": [100, 100, 100],
    })

    result = create_subpool_definitions(df, grouping_column="Project ID")

    assert "SubPool ID" in result.columns
    assert len(result) == 3
    # All should be in same sub-pool
    assert (result["SubPool ID"] == "ProjectA_pool").all()


def test_create_subpool_definitions_multiple_groups():
    """Test sub-pool creation with multiple groups."""
    df = pd.DataFrame({
        "Project ID": ["ProjectA", "ProjectA", "ProjectB", "ProjectB"],
        "Library Name": ["Lib1", "Lib2", "Lib3", "Lib4"],
        "Adjusted lib nM": [10.0, 20.0, 30.0, 40.0],
        "Target Reads (M)": [100, 100, 100, 100],
    })

    result = create_subpool_definitions(df, grouping_column="Project ID")

    assert "SubPool ID" in result.columns
    assert len(result) == 4

    # Check that each project has its own sub-pool
    proj_a = result[result["Project ID"] == "ProjectA"]
    assert (proj_a["SubPool ID"] == "ProjectA_pool").all()

    proj_b = result[result["Project ID"] == "ProjectB"]
    assert (proj_b["SubPool ID"] == "ProjectB_pool").all()


def test_create_subpool_definitions_large_group_split():
    """Test that large groups are split into multiple sub-pools."""
    # Create 150 libraries in one project (max is 96)
    num_libs = 150
    df = pd.DataFrame({
        "Project ID": ["ProjectA"] * num_libs,
        "Library Name": [f"Lib{i}" for i in range(num_libs)],
        "Adjusted lib nM": [10.0] * num_libs,
        "Target Reads (M)": [100] * num_libs,
    })

    result = create_subpool_definitions(
        df,
        grouping_column="Project ID",
        max_libraries_per_subpool=96
    )

    assert "SubPool ID" in result.columns
    assert len(result) == 150

    # Should create 2 sub-pools (96 + 54)
    unique_subpools = result["SubPool ID"].unique()
    assert len(unique_subpools) == 2
    assert "ProjectA_pool_1" in unique_subpools
    assert "ProjectA_pool_2" in unique_subpools

    # Check sizes
    pool1_size = len(result[result["SubPool ID"] == "ProjectA_pool_1"])
    pool2_size = len(result[result["SubPool ID"] == "ProjectA_pool_2"])
    assert pool1_size == 96
    assert pool2_size == 54


def test_create_subpool_definitions_missing_column_raises_error():
    """Test that missing grouping column raises ValueError."""
    df = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [10.0, 20.0],
    })

    with pytest.raises(ValueError, match="Grouping column 'Project ID' not found"):
        create_subpool_definitions(df, grouping_column="Project ID")


def test_create_subpool_definitions_custom_grouping_column():
    """Test sub-pool creation with custom grouping column."""
    df = pd.DataFrame({
        "Sample Type": ["TypeA", "TypeA", "TypeB"],
        "Library Name": ["Lib1", "Lib2", "Lib3"],
        "Adjusted lib nM": [10.0, 20.0, 30.0],
        "Target Reads (M)": [100, 100, 100],
    })

    result = create_subpool_definitions(df, grouping_column="Sample Type")

    assert "SubPool ID" in result.columns
    assert len(result) == 3

    type_a = result[result["Sample Type"] == "TypeA"]
    assert (type_a["SubPool ID"] == "TypeA_pool").all()

    type_b = result[result["Sample Type"] == "TypeB"]
    assert (type_b["SubPool ID"] == "TypeB_pool").all()


# ============================================================================
# Test compute_subpool_properties
# ============================================================================


def test_compute_subpool_properties_equimolar():
    """Test sub-pool molarity calculation for equimolar libraries."""
    # Create libraries DataFrame
    df_libraries = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2", "Lib3"],
        "Adjusted lib nM": [10.0, 10.0, 10.0],
        "Target Reads (M)": [100, 100, 100],
        "Project ID": ["ProjectA", "ProjectA", "ProjectA"],
    })

    # Create volumes DataFrame (all equal volumes for equimolar)
    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2", "Lib3"],
        "Final Volume (µl)": [5.0, 5.0, 5.0],
    })

    result = compute_subpool_properties(
        df_libraries,
        df_volumes,
        subpool_id="ProjectA_pool"
    )

    # Check type
    assert isinstance(result, SubPoolRecord)

    # Check properties
    assert result.subpool_id == "ProjectA_pool"
    assert result.member_libraries == ["Lib1", "Lib2", "Lib3"]
    assert result.total_volume_ul == 15.0  # 5 + 5 + 5

    # Molarity: (10*5 + 10*5 + 10*5) / 15 = 150/15 = 10 nM
    assert pytest.approx(result.calculated_nm, rel=1e-6) == 10.0

    # Target reads: 100 + 100 + 100 = 300
    assert result.target_reads_m == 300.0

    # Project ID should be preserved
    assert result.parent_project_id == "ProjectA"


def test_compute_subpool_properties_different_concentrations():
    """Test sub-pool molarity with different concentrations."""
    df_libraries = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [20.0, 40.0],
        "Target Reads (M)": [100, 100],
        "Project ID": ["ProjectA", "ProjectA"],
    })

    # Equal volumes
    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Final Volume (µl)": [10.0, 10.0],
    })

    result = compute_subpool_properties(
        df_libraries,
        df_volumes,
        subpool_id="ProjectA_pool"
    )

    # Total volume: 10 + 10 = 20 µl
    assert result.total_volume_ul == 20.0

    # Molarity: (20*10 + 40*10) / 20 = 600/20 = 30 nM
    assert pytest.approx(result.calculated_nm, rel=1e-6) == 30.0


def test_compute_subpool_properties_different_volumes():
    """Test sub-pool molarity with different volumes (weighted)."""
    df_libraries = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [10.0, 10.0],
        "Target Reads (M)": [100, 200],  # Lib2 needs 2x reads
        "Project ID": ["ProjectA", "ProjectA"],
    })

    # Lib2 gets 2x volume for 2x reads
    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Final Volume (µl)": [5.0, 10.0],
    })

    result = compute_subpool_properties(
        df_libraries,
        df_volumes,
        subpool_id="ProjectA_pool"
    )

    # Total volume: 5 + 10 = 15 µl
    assert result.total_volume_ul == 15.0

    # Molarity: (10*5 + 10*10) / 15 = 150/15 = 10 nM
    assert pytest.approx(result.calculated_nm, rel=1e-6) == 10.0

    # Target reads: 100 + 200 = 300
    assert result.target_reads_m == 300.0


def test_compute_subpool_properties_missing_library_column():
    """Test error when Library Name column is missing."""
    df_libraries = pd.DataFrame({
        "Adjusted lib nM": [10.0],
        "Target Reads (M)": [100],
    })

    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1"],
        "Final Volume (µl)": [5.0],
    })

    with pytest.raises(ValueError, match="Missing required library columns"):
        compute_subpool_properties(df_libraries, df_volumes, "pool")


def test_compute_subpool_properties_missing_volume_column():
    """Test error when Final Volume column is missing."""
    df_libraries = pd.DataFrame({
        "Library Name": ["Lib1"],
        "Adjusted lib nM": [10.0],
        "Target Reads (M)": [100],
    })

    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1"],
        # Missing "Final Volume (µl)"
    })

    with pytest.raises(ValueError, match="Missing required volume columns"):
        compute_subpool_properties(df_libraries, df_volumes, "pool")


# ============================================================================
# Test compute_hierarchical_pooling (integration)
# ============================================================================


def test_compute_hierarchical_pooling_basic():
    """Test complete hierarchical pooling workflow with simple data."""
    # 6 libraries across 2 projects
    df = pd.DataFrame({
        "Project ID": ["ProjA", "ProjA", "ProjA", "ProjB", "ProjB", "ProjB"],
        "Library Name": ["A1", "A2", "A3", "B1", "B2", "B3"],
        "Adjusted lib nM": [10.0, 20.0, 30.0, 15.0, 25.0, 35.0],
        "Target Reads (M)": [100, 100, 100, 100, 100, 100],
    })

    result = compute_hierarchical_pooling(
        df,
        grouping_column="Project ID",
        scaling_factor=0.1,
    )

    # Check result type
    assert isinstance(result, HierarchicalPoolingPlan)

    # Check basic properties
    assert result.total_libraries == 6
    assert result.total_subpools == 2
    assert result.strategy == "hierarchical"
    assert result.grouping_method == "Project ID"

    # Check stages
    assert len(result.stages) == 2
    assert result.stages[0].stage == PoolingStage.LIBRARY_TO_SUBPOOL
    assert result.stages[1].stage == PoolingStage.SUBPOOL_TO_MASTER

    # Stage 1: 6 libraries → 2 sub-pools
    assert result.stages[0].input_count == 6
    assert result.stages[0].output_count == 2
    assert result.stages[0].total_pipetting_steps == 6

    # Stage 2: 2 sub-pools → 1 master
    assert result.stages[1].input_count == 2
    assert result.stages[1].output_count == 1
    assert result.stages[1].total_pipetting_steps == 2

    # Total pipetting: 6 + 2 = 8 (much less than 6 in single-stage)
    assert result.total_pipetting_steps == 8


def test_compute_hierarchical_pooling_large_project_split():
    """Test that large projects are automatically split."""
    # 150 libraries in one project
    num_libs = 150
    df = pd.DataFrame({
        "Project ID": ["BigProject"] * num_libs,
        "Library Name": [f"Lib{i:03d}" for i in range(num_libs)],
        "Adjusted lib nM": [10.0] * num_libs,
        "Target Reads (M)": [100] * num_libs,
    })

    result = compute_hierarchical_pooling(
        df,
        grouping_column="Project ID",
        scaling_factor=0.1,
    )

    # Should create 2 sub-pools (96 + 54)
    assert result.total_libraries == 150
    assert result.total_subpools == 2

    # Stage 1: 150 libraries → 2 sub-pools
    assert result.stages[0].input_count == 150
    assert result.stages[0].output_count == 2


def test_compute_hierarchical_pooling_multiple_projects():
    """Test hierarchical pooling with multiple projects."""
    # Create 4 projects with varying numbers of libraries
    df = pd.DataFrame({
        "Project ID": (
            ["ProjA"] * 10 +
            ["ProjB"] * 20 +
            ["ProjC"] * 15 +
            ["ProjD"] * 5
        ),
        "Library Name": [f"Lib{i:03d}" for i in range(50)],
        "Adjusted lib nM": [15.0] * 50,
        "Target Reads (M)": [100] * 50,
    })

    result = compute_hierarchical_pooling(
        df,
        grouping_column="Project ID",
        scaling_factor=0.1,
    )

    # Should create 4 sub-pools (one per project, none exceed 96)
    assert result.total_libraries == 50
    assert result.total_subpools == 4

    # Stage 1: 50 libraries → 4 sub-pools
    assert result.stages[0].input_count == 50
    assert result.stages[0].output_count == 4

    # Stage 2: 4 sub-pools → 1 master
    assert result.stages[1].input_count == 4
    assert result.stages[1].output_count == 1

    # Total pipetting: 50 + 4 = 54 steps
    assert result.total_pipetting_steps == 54


def test_compute_hierarchical_pooling_validates_parameters():
    """Test that scaling_factor and min_volume are properly passed through."""
    df = pd.DataFrame({
        "Project ID": ["ProjA", "ProjA"],
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [10.0, 20.0],
        "Target Reads (M)": [100, 100],
    })

    result = compute_hierarchical_pooling(
        df,
        grouping_column="Project ID",
        scaling_factor=0.5,  # Non-default
        min_volume_ul=0.01,
        max_volume_ul=50.0,
    )

    # Check parameters were stored
    assert result.parameters["scaling_factor"] == 0.5
    assert result.parameters["min_volume_ul"] == 0.01
    assert result.parameters["max_volume_ul"] == 50.0


def test_compute_hierarchical_pooling_missing_column_raises_error():
    """Test error when grouping column doesn't exist."""
    df = pd.DataFrame({
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [10.0, 20.0],
        "Target Reads (M)": [100, 100],
    })

    with pytest.raises(ValueError, match="Grouping column 'Project ID' not found"):
        compute_hierarchical_pooling(df, grouping_column="Project ID")


def test_compute_hierarchical_pooling_missing_required_column_raises_error():
    """Test error when required column is missing."""
    df = pd.DataFrame({
        "Project ID": ["ProjA", "ProjA"],
        "Library Name": ["Lib1", "Lib2"],
        # Missing "Adjusted lib nM" and "Target Reads (M)"
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_hierarchical_pooling(df, grouping_column="Project ID")


def test_compute_hierarchical_pooling_preserves_stage_order():
    """Test that stages are properly ordered."""
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 5,
        "Library Name": [f"Lib{i}" for i in range(5)],
        "Adjusted lib nM": [10.0] * 5,
        "Target Reads (M)": [100] * 5,
    })

    result = compute_hierarchical_pooling(df, grouping_column="Project ID")

    # Stages should be numbered 1, 2
    assert result.stages[0].stage_number == 1
    assert result.stages[1].stage_number == 2

    # Stage types should be in correct order
    assert result.stages[0].stage == PoolingStage.LIBRARY_TO_SUBPOOL
    assert result.stages[1].stage == PoolingStage.SUBPOOL_TO_MASTER


def test_compute_hierarchical_pooling_with_total_reads():
    """Test hierarchical pooling with total_reads_m parameter."""
    df = pd.DataFrame({
        "Project ID": ["ProjA", "ProjA", "ProjB", "ProjB"],
        "Library Name": ["A1", "A2", "B1", "B2"],
        "Adjusted lib nM": [10.0, 20.0, 30.0, 40.0],
        "Target Reads (M)": [100, 100, 100, 100],
    })

    result = compute_hierarchical_pooling(
        df,
        grouping_column="Project ID",
        scaling_factor=0.1,
        total_reads_m=1000.0,  # Specify total reads
    )

    # Check that total_reads_m was stored
    assert result.parameters["total_reads_m"] == 1000.0

    # The result should include expected reads calculations
    # (This would be validated by checking the volumes_df_json,
    # but we trust compute_pool_volumes to handle that correctly)
    assert result is not None


def test_compute_hierarchical_pooling_timestamp():
    """Test that creation timestamp is set."""
    df = pd.DataFrame({
        "Project ID": ["ProjA", "ProjA"],
        "Library Name": ["Lib1", "Lib2"],
        "Adjusted lib nM": [10.0, 20.0],
        "Target Reads (M)": [100, 100],
    })

    before = datetime.now()
    result = compute_hierarchical_pooling(df, grouping_column="Project ID")
    after = datetime.now()

    # Timestamp should be between before and after
    assert before <= result.created_at <= after


# ============================================================================
# Test edge cases
# ============================================================================


def test_create_subpool_definitions_exactly_max_size():
    """Test group exactly at max size (edge case)."""
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 96,
        "Library Name": [f"Lib{i:03d}" for i in range(96)],
        "Adjusted lib nM": [10.0] * 96,
        "Target Reads (M)": [100] * 96,
    })

    result = create_subpool_definitions(
        df,
        grouping_column="Project ID",
        max_libraries_per_subpool=96
    )

    # Should create exactly 1 sub-pool (not split)
    unique_subpools = result["SubPool ID"].unique()
    assert len(unique_subpools) == 1
    assert unique_subpools[0] == "ProjA_pool"


def test_create_subpool_definitions_just_over_max_size():
    """Test group just over max size (should split)."""
    df = pd.DataFrame({
        "Project ID": ["ProjA"] * 97,
        "Library Name": [f"Lib{i:03d}" for i in range(97)],
        "Adjusted lib nM": [10.0] * 97,
        "Target Reads (M)": [100] * 97,
    })

    result = create_subpool_definitions(
        df,
        grouping_column="Project ID",
        max_libraries_per_subpool=96
    )

    # Should create 2 sub-pools (96 + 1)
    unique_subpools = result["SubPool ID"].unique()
    assert len(unique_subpools) == 2


def test_compute_subpool_properties_zero_volume():
    """Test sub-pool properties when total volume is zero (validation error)."""
    df_libraries = pd.DataFrame({
        "Library Name": ["Lib1"],
        "Adjusted lib nM": [10.0],
        "Target Reads (M)": [100],
    })

    df_volumes = pd.DataFrame({
        "Library Name": ["Lib1"],
        "Final Volume (µl)": [0.0],  # Zero volume
    })

    # Should raise validation error because total_volume_ul must be > 0
    with pytest.raises(Exception):  # Pydantic ValidationError
        compute_subpool_properties(
            df_libraries,
            df_volumes,
            subpool_id="pool"
        )
