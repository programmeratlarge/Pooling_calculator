"""
Unit tests for computation engine.

Tests molarity calculations, volume distribution, and project aggregation.
"""

import pytest
import pandas as pd
import numpy as np

from pooling_calculator.compute import (
    compute_molarity_from_concentration,
    compute_effective_molarity,
    compute_pool_volumes,
    summarize_by_project,
)
from pooling_calculator.config import MW_PER_BP


# ============================================================================
# compute_molarity_from_concentration Tests
# ============================================================================


def test_compute_molarity_basic():
    """compute_molarity_from_concentration should calculate correct molarity."""
    # Example: 1.0 ng/µl at 200 bp
    # = (1.0 × 10^6) / (660 × 200)
    # = 1000000 / 132000
    # ≈ 7.576 nM

    result = compute_molarity_from_concentration(1.0, 200)

    assert pytest.approx(result, rel=1e-3) == 7.576


def test_compute_molarity_real_example():
    """compute_molarity_from_concentration should match expected output for EF19."""
    # From 7050I data: EF19 has 1.7766 ng/µl at 198 bp
    # Expected: 13.595 nM

    result = compute_molarity_from_concentration(1.7766, 198)

    assert pytest.approx(result, rel=1e-3) == 13.595


def test_compute_molarity_zero_concentration():
    """compute_molarity_from_concentration should reject zero concentration."""
    with pytest.raises(ValueError, match="Concentration must be > 0"):
        compute_molarity_from_concentration(0, 200)


def test_compute_molarity_negative_concentration():
    """compute_molarity_from_concentration should reject negative concentration."""
    with pytest.raises(ValueError, match="Concentration must be > 0"):
        compute_molarity_from_concentration(-1.0, 200)


def test_compute_molarity_zero_fragment_size():
    """compute_molarity_from_concentration should reject zero fragment size."""
    with pytest.raises(ValueError, match="Fragment size must be > 0"):
        compute_molarity_from_concentration(1.0, 0)


def test_compute_molarity_negative_fragment_size():
    """compute_molarity_from_concentration should reject negative fragment size."""
    with pytest.raises(ValueError, match="Fragment size must be > 0"):
        compute_molarity_from_concentration(1.0, -200)


# ============================================================================
# compute_effective_molarity Tests
# ============================================================================


def test_compute_effective_molarity_calculated_only():
    """compute_effective_molarity should use calculated nM when no empirical provided."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Final ng/ul": [1.0, 2.0],
        "Adjusted peak size": [200, 200],
    })

    result = compute_effective_molarity(df)

    assert "Calculated nM" in result.columns
    assert "Effective nM (Use)" in result.columns
    assert "Adjusted lib nM" in result.columns

    # Check calculated values
    assert pytest.approx(result["Calculated nM"].iloc[0], rel=1e-3) == 7.576
    assert pytest.approx(result["Calculated nM"].iloc[1], rel=1e-3) == 15.152

    # Effective should match calculated (no empirical)
    assert result["Effective nM (Use)"].iloc[0] == result["Calculated nM"].iloc[0]
    assert result["Effective nM (Use)"].iloc[1] == result["Calculated nM"].iloc[1]


def test_compute_effective_molarity_empirical_override():
    """compute_effective_molarity should use empirical nM when provided."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Final ng/ul": [1.0, 2.0],
        "Adjusted peak size": [200, 200],
        "Empirical Library nM": [10.0, None],  # Only Lib001 has empirical
    })

    result = compute_effective_molarity(df)

    # Lib001 should use empirical
    assert result["Effective nM (Use)"].iloc[0] == 10.0

    # Lib002 should use calculated
    assert pytest.approx(result["Effective nM (Use)"].iloc[1], rel=1e-3) == 15.152


def test_compute_effective_molarity_empirical_zero_ignored():
    """compute_effective_molarity should ignore zero empirical nM."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        "Final ng/ul": [1.0],
        "Adjusted peak size": [200],
        "Empirical Library nM": [0],  # Zero should be ignored
    })

    result = compute_effective_molarity(df)

    # Should use calculated, not zero empirical
    assert pytest.approx(result["Effective nM (Use)"].iloc[0], rel=1e-3) == 7.576


def test_compute_effective_molarity_missing_columns():
    """compute_effective_molarity should raise error if required columns missing."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        # Missing "Final ng/ul"
        "Adjusted peak size": [200],
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_effective_molarity(df)


def test_compute_effective_molarity_real_data():
    """compute_effective_molarity should match expected values for 7050I data."""
    # Test with first 3 libraries from 7050I
    df = pd.DataFrame({
        "Library Name": ["EF19", "EF20", "EF21"],
        "Final ng/ul": [1.7766, 1.7037, 1.61175],
        "Adjusted peak size": [198, 198, 198],
    })

    result = compute_effective_molarity(df)

    # Expected values from 7050I_expected_outputs.csv
    assert pytest.approx(result["Calculated nM"].iloc[0], rel=1e-3) == 13.595
    assert pytest.approx(result["Calculated nM"].iloc[1], rel=1e-3) == 13.037
    assert pytest.approx(result["Calculated nM"].iloc[2], rel=1e-3) == 12.334


# ============================================================================
# compute_pool_volumes Tests
# ============================================================================


def test_compute_pool_volumes_equimolar():
    """compute_pool_volumes should produce equal volumes for equimolar pooling."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Effective nM (Use)": [10.0, 10.0],  # Same concentration
        "Target Reads (M)": [100, 100],  # Same target
    })

    result = compute_pool_volumes(df, desired_pool_volume_ul=10.0)

    # Should get equal volumes
    assert pytest.approx(result["Stock Volume (µl)"].iloc[0], rel=1e-6) == 5.0
    assert pytest.approx(result["Stock Volume (µl)"].iloc[1], rel=1e-6) == 5.0

    # Pool fractions should be equal
    assert pytest.approx(result["Pool Fraction"].iloc[0], rel=1e-6) == 0.5
    assert pytest.approx(result["Pool Fraction"].iloc[1], rel=1e-6) == 0.5


def test_compute_pool_volumes_weighted_by_target():
    """compute_pool_volumes should adjust volumes based on target reads."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Effective nM (Use)": [10.0, 10.0],  # Same concentration
        "Target Reads (M)": [100, 10],  # 10x difference in target
    })

    result = compute_pool_volumes(df, desired_pool_volume_ul=11.0)

    # Lib001 should get ~10x more volume than Lib002
    vol1 = result["Stock Volume (µl)"].iloc[0]
    vol2 = result["Stock Volume (µl)"].iloc[1]

    assert pytest.approx(vol1 / vol2, rel=1e-3) == 10.0

    # Volumes should sum to desired pool volume
    assert pytest.approx(vol1 + vol2, rel=1e-6) == 11.0


def test_compute_pool_volumes_weighted_by_concentration():
    """compute_pool_volumes should adjust volumes inversely with concentration."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Effective nM (Use)": [10.0, 20.0],  # 2x concentration difference
        "Target Reads (M)": [100, 100],  # Same target
    })

    result = compute_pool_volumes(df, desired_pool_volume_ul=15.0)

    # Lib001 (lower conc) should get 2x more volume than Lib002 (higher conc)
    vol1 = result["Stock Volume (µl)"].iloc[0]
    vol2 = result["Stock Volume (µl)"].iloc[1]

    assert pytest.approx(vol1 / vol2, rel=1e-3) == 2.0


def test_compute_pool_volumes_insufficient_volume_flag():
    """compute_pool_volumes should flag libraries with insufficient volume."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        "Effective nM (Use)": [1.0],
        "Target Reads (M)": [100],
        "Total Volume": [5.0],  # Only 5 µl available
    })

    # Request 10 µl pool, which would require more than 5 µl from this single library
    result = compute_pool_volumes(df, desired_pool_volume_ul=10.0)

    # Should have flag about insufficient volume
    assert "Insufficient volume" in result["Flags"].iloc[0]


def test_compute_pool_volumes_below_min_volume_flag():
    """compute_pool_volumes should flag libraries below minimum pipettable volume."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Effective nM (Use)": [1000.0, 10.0],  # Lib001 very high, Lib002 low
        "Target Reads (M)": [1, 100],  # Lib001 low target, Lib002 high target
    })

    # Lib001 should get a very small volume (high conc, low target)
    # Lib002 should get most of the volume (low conc, high target)
    result = compute_pool_volumes(df, desired_pool_volume_ul=10.0, min_volume_ul=0.1)

    # Lib001 should have flag about being below minimum
    assert "Below minimum pipettable volume" in result["Flags"].iloc[0]
    # Lib002 should have no flags
    assert result["Flags"].iloc[1] == ""


def test_compute_pool_volumes_exceeds_max_volume_flag():
    """compute_pool_volumes should flag libraries exceeding maximum volume."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        "Effective nM (Use)": [1.0],  # Very low concentration
        "Target Reads (M)": [100],  # High target
    })

    # This would normally require a large volume
    result = compute_pool_volumes(df, desired_pool_volume_ul=10.0, max_volume_ul=5.0)

    # Should have flag about exceeding maximum
    assert "Exceeds maximum volume" in result["Flags"].iloc[0]


def test_compute_pool_volumes_expected_reads():
    """compute_pool_volumes should calculate expected reads when total provided."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Effective nM (Use)": [10.0, 10.0],
        "Target Reads (M)": [100, 100],
    })

    result = compute_pool_volumes(df, desired_pool_volume_ul=10.0, total_reads_m=500)

    # Each library should get 50% of total reads (equimolar)
    assert pytest.approx(result["Expected Reads (M)"].iloc[0], rel=1e-6) == 250
    assert pytest.approx(result["Expected Reads (M)"].iloc[1], rel=1e-6) == 250


def test_compute_pool_volumes_invalid_pool_volume():
    """compute_pool_volumes should reject invalid pool volume."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        "Effective nM (Use)": [10.0],
        "Target Reads (M)": [100],
    })

    with pytest.raises(ValueError, match="Desired pool volume must be > 0"):
        compute_pool_volumes(df, desired_pool_volume_ul=0)


def test_compute_pool_volumes_invalid_min_volume():
    """compute_pool_volumes should reject negative min volume."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        "Effective nM (Use)": [10.0],
        "Target Reads (M)": [100],
    })

    with pytest.raises(ValueError, match="Min volume must be >= 0"):
        compute_pool_volumes(df, desired_pool_volume_ul=10.0, min_volume_ul=-1.0)


def test_compute_pool_volumes_missing_columns():
    """compute_pool_volumes should raise error if required columns missing."""
    df = pd.DataFrame({
        "Library Name": ["Lib001"],
        # Missing "Effective nM (Use)"
        "Target Reads (M)": [100],
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_pool_volumes(df, desired_pool_volume_ul=10.0)


def test_compute_pool_volumes_real_data_sample():
    """compute_pool_volumes should produce volumes matching 7050I expected outputs."""
    # Test with first 3 libraries from 7050I
    df = pd.DataFrame({
        "Library Name": ["EF19", "EF20", "EF21"],
        "Effective nM (Use)": [13.595, 13.037, 12.334],
        "Target Reads (M)": [100, 10, 100],
        "Total Volume": [20, 20, 20],
    })

    # From data/README.md: pool_param = 0.1 (need to determine actual desired_pool_volume)
    # Total expected volume sum from data: 18.785 µl
    # Let's compute what the sum should be
    v_raw_19 = 100 / 13.595
    v_raw_20 = 10 / 13.037
    v_raw_21 = 100 / 12.334
    v_raw_total = v_raw_19 + v_raw_20 + v_raw_21

    # Expected volumes from CSV:
    # EF19: 0.736 µl
    # EF20: 0.077 µl
    # EF21: 0.811 µl
    # Sum: 1.624 µl

    expected_sum = 0.736 + 0.077 + 0.811

    result = compute_pool_volumes(df, desired_pool_volume_ul=expected_sum)

    # Check volumes match expected (within tolerance)
    assert pytest.approx(result["Stock Volume (µl)"].iloc[0], rel=1e-2) == 0.736
    assert pytest.approx(result["Stock Volume (µl)"].iloc[1], rel=1e-2) == 0.077
    assert pytest.approx(result["Stock Volume (µl)"].iloc[2], rel=1e-2) == 0.811


# ============================================================================
# summarize_by_project Tests
# ============================================================================


def test_summarize_by_project_single_project():
    """summarize_by_project should aggregate libraries within a project."""
    df = pd.DataFrame({
        "Project ID": ["ProjectA", "ProjectA", "ProjectA"],
        "Library Name": ["Lib001", "Lib002", "Lib003"],
        "Stock Volume (µl)": [1.0, 2.0, 3.0],
        "Pool Fraction": [0.1, 0.2, 0.3],
        "Expected Reads (M)": [50, 100, 150],
    })

    result = summarize_by_project(df)

    assert len(result) == 1
    assert result["Project ID"].iloc[0] == "ProjectA"
    assert result["Number of Libraries"].iloc[0] == 3
    assert pytest.approx(result["Total Volume (µl)"].iloc[0], rel=1e-6) == 6.0
    assert pytest.approx(result["Pool Fraction"].iloc[0], rel=1e-6) == 0.6
    assert pytest.approx(result["Expected Reads (M)"].iloc[0], rel=1e-6) == 300


def test_summarize_by_project_multiple_projects():
    """summarize_by_project should create separate rows for each project."""
    df = pd.DataFrame({
        "Project ID": ["ProjectA", "ProjectA", "ProjectB", "ProjectB"],
        "Library Name": ["Lib001", "Lib002", "Lib003", "Lib004"],
        "Stock Volume (µl)": [1.0, 2.0, 3.0, 4.0],
        "Pool Fraction": [0.1, 0.2, 0.3, 0.4],
    })

    result = summarize_by_project(df)

    assert len(result) == 2

    # Check ProjectA
    proj_a = result[result["Project ID"] == "ProjectA"].iloc[0]
    assert proj_a["Number of Libraries"] == 2
    assert pytest.approx(proj_a["Total Volume (µl)"], rel=1e-6) == 3.0
    assert pytest.approx(proj_a["Pool Fraction"], rel=1e-6) == 0.3

    # Check ProjectB
    proj_b = result[result["Project ID"] == "ProjectB"].iloc[0]
    assert proj_b["Number of Libraries"] == 2
    assert pytest.approx(proj_b["Total Volume (µl)"], rel=1e-6) == 7.0
    assert pytest.approx(proj_b["Pool Fraction"], rel=1e-6) == 0.7


def test_summarize_by_project_missing_project_id():
    """summarize_by_project should raise error if Project ID column missing."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002"],
        "Stock Volume (µl)": [1.0, 2.0],
    })

    with pytest.raises(ValueError, match="Missing required column: Project ID"):
        summarize_by_project(df)


def test_summarize_by_project_no_expected_reads():
    """summarize_by_project should work without Expected Reads column."""
    df = pd.DataFrame({
        "Project ID": ["ProjectA"],
        "Library Name": ["Lib001"],
        "Stock Volume (µl)": [1.0],
        "Pool Fraction": [1.0],
        # No "Expected Reads (M)" column
    })

    result = summarize_by_project(df)

    assert len(result) == 1
    assert "Expected Reads (M)" not in result.columns
