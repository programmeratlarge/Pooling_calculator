"""
Unit tests for validation module.

Tests column presence, row-level validation, uniqueness checks,
and comprehensive error/warning messages.
"""

import pytest
import pandas as pd

from pooling_calculator.validation import (
    validate_columns,
    validate_row_data_types,
    validate_uniqueness,
    run_all_validations,
)


# ============================================================================
# validate_columns Tests
# ============================================================================


def test_validate_columns_all_present():
    """validate_columns should return no errors when all required columns present."""
    df = pd.DataFrame(columns=[
        "Project ID",
        "Library Name",
        "Final ng/ul",
        "Total Volume",
        "Barcodes",
        "Adjusted peak size",
        "Target Reads (M)",
    ])

    errors = validate_columns(df)

    assert len(errors) == 0


def test_validate_columns_missing_one():
    """validate_columns should detect missing required column."""
    df = pd.DataFrame(columns=[
        "Project ID",
        "Library Name",
        "Final ng/ul",
        # Missing "Total Volume"
        "Barcodes",
        "Adjusted peak size",
        "Target Reads (M)",
    ])

    errors = validate_columns(df)

    assert len(errors) == 1
    assert "Total Volume" in errors[0]


def test_validate_columns_missing_multiple():
    """validate_columns should detect multiple missing columns."""
    df = pd.DataFrame(columns=[
        "Project ID",
        "Library Name",
        # Missing several columns
    ])

    errors = validate_columns(df)

    assert len(errors) == 5  # 5 missing columns


def test_validate_columns_case_insensitive():
    """validate_columns should handle different case variations."""
    df = pd.DataFrame(columns=[
        "project id",  # lowercase
        "LIBRARY NAME",  # uppercase
        "Final ng/ul",
        "Total Volume",
        "Barcodes",
        "Adjusted peak size",
        "Target Reads (M)",
    ])

    errors = validate_columns(df)

    # Should accept case variations
    assert len(errors) == 0


# ============================================================================
# validate_row_data_types Tests
# ============================================================================


def test_validate_row_data_types_valid_data():
    """validate_row_data_types should return no errors for valid data."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) == 0
    # Might have warnings for concentration/size ranges
    assert isinstance(warnings, list)


def test_validate_row_data_types_empty_project_id():
    """validate_row_data_types should catch empty Project ID."""
    df = pd.DataFrame({
        "Project ID": [""],  # Empty
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Project ID" in err and "empty" in err.lower() for err in errors)


def test_validate_row_data_types_negative_concentration():
    """validate_row_data_types should catch negative concentration."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [-5.0],  # Negative
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Final ng/ul" in err and ("negative" in err.lower() or ">" in err) for err in errors)


def test_validate_row_data_types_invalid_concentration_type():
    """validate_row_data_types should catch non-numeric concentration."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": ["not_a_number"],  # Invalid type
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Final ng/ul" in err and "parse" in err.lower() for err in errors)


def test_validate_row_data_types_very_low_concentration_warning():
    """validate_row_data_types should warn for very low concentration."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [0.05],  # Very low
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) == 0  # No errors, but should have warning
    assert len(warnings) >= 1
    assert any("concentration" in warn.lower() for warn in warnings)


def test_validate_row_data_types_very_high_concentration_warning():
    """validate_row_data_types should warn for very high concentration."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [2000.0],  # Very high
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) == 0
    assert len(warnings) >= 1
    assert any("concentration" in warn.lower() or "high" in warn.lower() for warn in warnings)


def test_validate_row_data_types_zero_volume():
    """validate_row_data_types should catch zero volume."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [0],  # Zero
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Total Volume" in err and (">" in err or "negative" in err.lower()) for err in errors)


def test_validate_row_data_types_low_volume_warning():
    """validate_row_data_types should warn for low total volume."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [2.0],  # Low
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) == 0
    assert len(warnings) >= 1
    assert any("volume" in warn.lower() for warn in warnings)


def test_validate_row_data_types_empty_barcode():
    """validate_row_data_types should catch empty barcode."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": [""],  # Empty
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Barcodes" in err and "empty" in err.lower() for err in errors)


def test_validate_row_data_types_small_fragment_size_error():
    """validate_row_data_types should catch fragment size below minimum."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [30],  # Below minimum (50)
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("peak size" in err.lower() or "fragment" in err.lower() for err in errors)


def test_validate_row_data_types_large_fragment_size_warning():
    """validate_row_data_types should warn for very large fragment size."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [15000],  # Very large
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) == 0
    assert len(warnings) >= 1
    assert any("fragment" in warn.lower() or "large" in warn.lower() for warn in warnings)


def test_validate_row_data_types_optional_empirical_nm():
    """validate_row_data_types should allow empty empirical nM (optional field)."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Empirical Library nM": [None],  # Optional, can be empty
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    # Should not error on empty empirical nM
    assert all("Empirical" not in err for err in errors)


def test_validate_row_data_types_invalid_empirical_nm():
    """validate_row_data_types should catch invalid empirical nM when provided."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Empirical Library nM": [-5.0],  # Negative (invalid)
        "Target Reads (M)": [100],
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Empirical" in err for err in errors)


def test_validate_row_data_types_zero_target_reads():
    """validate_row_data_types should catch zero target reads."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [10.5],
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [0],  # Zero
    })

    errors, warnings = validate_row_data_types(df)

    assert len(errors) >= 1
    assert any("Target Reads" in err for err in errors)


# ============================================================================
# validate_uniqueness Tests
# ============================================================================


def test_validate_uniqueness_all_unique():
    """validate_uniqueness should return no errors when all values unique."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002", "Lib003"],
        "Barcodes": ["ATCG", "CGTA", "TAGC"],
    })

    errors = validate_uniqueness(df)

    assert len(errors) == 0


def test_validate_uniqueness_duplicate_library_name():
    """validate_uniqueness should catch duplicate library names."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002", "Lib001"],  # Duplicate
        "Barcodes": ["ATCG", "CGTA", "TAGC"],
    })

    errors = validate_uniqueness(df)

    assert len(errors) >= 1
    assert any("Library Name" in err and "Lib001" in err for err in errors)


def test_validate_uniqueness_duplicate_barcode():
    """validate_uniqueness should catch duplicate barcodes."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002", "Lib003"],
        "Barcodes": ["ATCG", "CGTA", "ATCG"],  # Duplicate
    })

    errors = validate_uniqueness(df)

    assert len(errors) >= 1
    assert any("Barcodes" in err and "ATCG" in err for err in errors)


def test_validate_uniqueness_multiple_duplicates():
    """validate_uniqueness should catch multiple sets of duplicates."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002", "Lib001", "Lib002"],  # Two duplicates
        "Barcodes": ["ATCG", "CGTA", "TAGC", "GGCC"],
    })

    errors = validate_uniqueness(df)

    assert len(errors) >= 2  # At least 2 duplicate errors
    assert any("Lib001" in err for err in errors)
    assert any("Lib002" in err for err in errors)


def test_validate_uniqueness_reports_row_numbers():
    """validate_uniqueness should report which rows have duplicates."""
    df = pd.DataFrame({
        "Library Name": ["Lib001", "Lib002", "Lib001"],
        "Barcodes": ["ATCG", "CGTA", "TAGC"],
    })

    errors = validate_uniqueness(df)

    assert len(errors) >= 1
    # Should mention rows 1 and 3 (1-indexed)
    assert any("1" in err and "3" in err for err in errors)


# ============================================================================
# run_all_validations Tests
# ============================================================================


def test_run_all_validations_valid_data():
    """run_all_validations should return valid result for good data."""
    df = pd.DataFrame({
        "Project ID": ["Project_A", "Project_A"],
        "Library Name": ["Lib001", "Lib002"],
        "Final ng/ul": [10.5, 12.3],
        "Total Volume": [20.0, 25.0],
        "Barcodes": ["ATCG", "CGTA"],
        "Adjusted peak size": [500, 550],
        "Target Reads (M)": [100, 100],
    })

    result = run_all_validations(df)

    assert result.is_valid is True
    assert len(result.errors) == 0
    # May have warnings
    assert isinstance(result.warnings, list)


def test_run_all_validations_missing_column():
    """run_all_validations should fail if required column missing."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        # Missing "Final ng/ul"
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    result = run_all_validations(df)

    assert result.is_valid is False
    assert len(result.errors) >= 1
    assert any("Final ng/ul" in err for err in result.errors)


def test_run_all_validations_invalid_row_data():
    """run_all_validations should fail for invalid row data."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [-10.5],  # Negative (invalid)
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    result = run_all_validations(df)

    assert result.is_valid is False
    assert len(result.errors) >= 1


def test_run_all_validations_duplicate_values():
    """run_all_validations should fail for duplicate library names."""
    df = pd.DataFrame({
        "Project ID": ["Project_A", "Project_A"],
        "Library Name": ["Lib001", "Lib001"],  # Duplicate
        "Final ng/ul": [10.5, 12.3],
        "Total Volume": [20.0, 25.0],
        "Barcodes": ["ATCG", "CGTA"],
        "Adjusted peak size": [500, 550],
        "Target Reads (M)": [100, 100],
    })

    result = run_all_validations(df)

    assert result.is_valid is False
    assert len(result.errors) >= 1
    assert any("Lib001" in err for err in result.errors)


def test_run_all_validations_with_warnings_still_valid():
    """run_all_validations should be valid with warnings but no errors."""
    df = pd.DataFrame({
        "Project ID": ["Project_A"],
        "Library Name": ["Lib001"],
        "Final ng/ul": [0.05],  # Very low (warning, not error)
        "Total Volume": [20.0],
        "Barcodes": ["ATCG"],
        "Adjusted peak size": [500],
        "Target Reads (M)": [100],
    })

    result = run_all_validations(df)

    assert result.is_valid is True  # Warnings don't make it invalid
    assert len(result.errors) == 0
    assert len(result.warnings) >= 1
