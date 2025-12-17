"""
Integration tests for the complete pooling calculator pipeline.

Tests the full workflow from file loading through computation to export.
"""

import pytest
from pathlib import Path
import pandas as pd

from pooling_calculator.io import (
    load_spreadsheet,
    normalize_dataframe_columns,
    export_results_to_excel,
)
from pooling_calculator.validation import run_all_validations
from pooling_calculator.compute import (
    compute_effective_molarity,
    compute_pool_volumes,
    summarize_by_project,
)


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_full_pipeline_with_valid_data():
    """Test complete pipeline: load → validate → compute → export."""
    # Load test fixture
    fixture_path = FIXTURES_DIR / "valid_pool.csv"
    df = load_spreadsheet(fixture_path)
    df_normalized = normalize_dataframe_columns(df)

    # Validate
    validation_result = run_all_validations(df_normalized)
    assert validation_result.is_valid
    assert len(validation_result.errors) == 0

    # Compute molarity
    df_with_molarity = compute_effective_molarity(df_normalized)
    assert "Calculated nM" in df_with_molarity.columns
    assert "Effective nM (Use)" in df_with_molarity.columns

    # All values should be positive
    assert (df_with_molarity["Calculated nM"] > 0).all()

    # Compute pool volumes
    df_with_volumes = compute_pool_volumes(
        df_with_molarity,
        desired_pool_volume_ul=10.0,
        min_volume_ul=0.01,
    )

    assert "Stock Volume (µl)" in df_with_volumes.columns
    assert "Pool Fraction" in df_with_volumes.columns

    # Check volume constraints
    total_volume = df_with_volumes["Stock Volume (µl)"].sum()
    assert pytest.approx(total_volume, rel=1e-6) == 10.0

    # Pool fractions should sum to 1
    total_fraction = df_with_volumes["Pool Fraction"].sum()
    assert pytest.approx(total_fraction, rel=1e-6) == 1.0

    # Project aggregation
    df_projects = summarize_by_project(df_with_volumes)

    assert len(df_projects) == 2  # ProjectA and ProjectB
    assert "Project ID" in df_projects.columns
    assert "Number of Libraries" in df_projects.columns

    # Export to Excel
    excel_bytes = export_results_to_excel(
        library_df=df_with_volumes,
        project_df=df_projects,
    )

    assert excel_bytes is not None
    assert len(excel_bytes) > 0

    # Verify it's valid Excel by reading it back
    import io
    df_read_back = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="PoolingPlan_Libraries")
    assert len(df_read_back) == len(df_with_volumes)


def test_pipeline_rejects_invalid_data_missing_column():
    """Test pipeline correctly rejects data with missing required column."""
    fixture_path = FIXTURES_DIR / "invalid_missing_column.csv"
    df = load_spreadsheet(fixture_path)
    df_normalized = normalize_dataframe_columns(df)

    # Validation should fail
    validation_result = run_all_validations(df_normalized)

    assert not validation_result.is_valid
    assert len(validation_result.errors) > 0
    assert any("Total Volume" in err for err in validation_result.errors)


def test_pipeline_rejects_duplicate_barcodes():
    """Test pipeline correctly rejects data with duplicate barcodes."""
    fixture_path = FIXTURES_DIR / "invalid_duplicate_barcode.csv"
    df = load_spreadsheet(fixture_path)
    df_normalized = normalize_dataframe_columns(df)

    # Validation should fail
    validation_result = run_all_validations(df_normalized)

    assert not validation_result.is_valid
    assert len(validation_result.errors) > 0
    assert any("Barcodes" in err and "duplicate" in err.lower() for err in validation_result.errors)


def test_weighted_pooling():
    """Test that weighted pooling produces correct volume ratios."""
    # Create test data with known target read differences
    df = pd.DataFrame({
        "Project ID": ["TestProject", "TestProject"],
        "Library Name": ["HighTarget", "LowTarget"],
        "Final ng/ul": [10.0, 10.0],  # Same concentration
        "Total Volume": [50.0, 50.0],
        "Barcodes": ["AAAA", "TTTT"],
        "Adjusted peak size": [500, 500],  # Same size
        "Target Reads (M)": [100, 10],  # 10x difference
    })

    df_normalized = normalize_dataframe_columns(df)

    # Validate
    validation_result = run_all_validations(df_normalized)
    assert validation_result.is_valid

    # Compute
    df_with_molarity = compute_effective_molarity(df_normalized)
    df_with_volumes = compute_pool_volumes(
        df_with_molarity,
        desired_pool_volume_ul=11.0,
    )

    # Libraries with 10x target reads difference should get ~10x volume difference
    vol_high = df_with_volumes[df_with_volumes["Library Name"] == "HighTarget"]["Stock Volume (µl)"].iloc[0]
    vol_low = df_with_volumes[df_with_volumes["Library Name"] == "LowTarget"]["Stock Volume (µl)"].iloc[0]

    volume_ratio = vol_high / vol_low
    assert pytest.approx(volume_ratio, rel=1e-3) == 10.0


def test_empirical_nm_override():
    """Test that empirical nM overrides calculated nM."""
    # Create test data with empirical nM
    df = pd.DataFrame({
        "Project ID": ["TestProject"],
        "Library Name": ["EmpiricalTest"],
        "Final ng/ul": [10.0],
        "Total Volume": [50.0],
        "Barcodes": ["CCCC"],
        "Adjusted peak size": [500],
        "Empirical Library nM": [50.0],  # Provide empirical value
        "Target Reads (M)": [100],
    })

    df_normalized = normalize_dataframe_columns(df)

    # Compute
    df_with_molarity = compute_effective_molarity(df_normalized)

    # Effective nM should use empirical value, not calculated
    assert df_with_molarity["Effective nM (Use)"].iloc[0] == 50.0
    # Calculated should be different
    assert df_with_molarity["Calculated nM"].iloc[0] != 50.0


def test_volume_flags():
    """Test that volume constraint violations are flagged."""
    # Create test data that will trigger volume warnings
    df = pd.DataFrame({
        "Project ID": ["TestProject"],
        "Library Name": ["LowVolTest"],
        "Final ng/ul": [0.1],  # Very low concentration
        "Total Volume": [5.0],  # Limited volume available
        "Barcodes": ["GGGG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],  # High target
    })

    df_normalized = normalize_dataframe_columns(df)

    # Compute
    df_with_molarity = compute_effective_molarity(df_normalized)
    df_with_volumes = compute_pool_volumes(
        df_with_molarity,
        desired_pool_volume_ul=10.0,
        max_volume_ul=3.0,  # Set max constraint
    )

    # Should have a flag about exceeding maximum volume
    flags = df_with_volumes["Flags"].iloc[0]
    assert "Exceeds maximum volume" in flags


def test_project_aggregation():
    """Test that project-level aggregation works correctly."""
    fixture_path = FIXTURES_DIR / "valid_pool.csv"
    df = load_spreadsheet(fixture_path)
    df_normalized = normalize_dataframe_columns(df)

    # Run full pipeline
    df_with_molarity = compute_effective_molarity(df_normalized)
    df_with_volumes = compute_pool_volumes(
        df_with_molarity,
        desired_pool_volume_ul=10.0,
    )

    df_projects = summarize_by_project(df_with_volumes)

    # Should have 2 projects
    assert len(df_projects) == 2

    # Check ProjectA
    proj_a = df_projects[df_projects["Project ID"] == "ProjectA"].iloc[0]
    assert proj_a["Number of Libraries"] == 3

    # Check ProjectB
    proj_b = df_projects[df_projects["Project ID"] == "ProjectB"].iloc[0]
    assert proj_b["Number of Libraries"] == 2

    # Total fractions should sum to 1
    total_fraction = df_projects["Pool Fraction"].sum()
    assert pytest.approx(total_fraction, rel=1e-6) == 1.0
