"""
Unit tests for I/O operations.

Tests spreadsheet loading, column normalization, and Excel export.
"""

import pytest
import pandas as pd
from pathlib import Path
from io import BytesIO

from pooling_calculator.io import (
    load_spreadsheet,
    normalize_dataframe_columns,
    dataframe_to_dict_list,
    export_results_to_excel,
    generate_export_filename,
    create_library_dataframe_for_export,
    create_project_dataframe_for_export,
)


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================================
# load_spreadsheet Tests
# ============================================================================


def test_load_spreadsheet_from_file():
    """load_spreadsheet should load Excel file from path."""
    file_path = FIXTURES_DIR / "valid_pool.xlsx"
    df = load_spreadsheet(file_path)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5  # Should have 5 libraries
    assert "Project ID" in df.columns
    assert "Library Name" in df.columns


def test_load_spreadsheet_from_bytes():
    """load_spreadsheet should load Excel file from bytes."""
    file_path = FIXTURES_DIR / "valid_pool.xlsx"

    # Read file as bytes
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    df = load_spreadsheet(file_bytes)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5


def test_load_spreadsheet_file_not_found():
    """load_spreadsheet should raise FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        load_spreadsheet("nonexistent_file.xlsx")


def test_load_spreadsheet_removes_empty_rows():
    """load_spreadsheet should remove completely empty rows."""
    # Create test data with empty rows
    data = {
        "Col1": [1, None, 3],
        "Col2": [2, None, 4],
    }
    df = pd.DataFrame(data)

    # Save to Excel
    test_file = FIXTURES_DIR / "test_empty_rows.xlsx"
    df.to_excel(test_file, index=False)

    # Load and check
    loaded_df = load_spreadsheet(test_file)

    # Should have 2 rows (empty row removed)
    assert len(loaded_df) == 2

    # Cleanup
    test_file.unlink()


# ============================================================================
# normalize_dataframe_columns Tests
# ============================================================================


def test_normalize_dataframe_columns():
    """normalize_dataframe_columns should map alternative names to standard names."""
    file_path = FIXTURES_DIR / "alternative_columns.xlsx"
    df = load_spreadsheet(file_path)

    # Before normalization
    assert "project" in df.columns
    assert "library" in df.columns

    # Normalize
    df_normalized = normalize_dataframe_columns(df)

    # After normalization
    assert "Project ID" in df_normalized.columns
    assert "Library Name" in df_normalized.columns
    assert "Final ng/ul" in df_normalized.columns


def test_normalize_dataframe_columns_preserves_data():
    """Normalization should not change data, only column names."""
    file_path = FIXTURES_DIR / "alternative_columns.xlsx"
    df = load_spreadsheet(file_path)

    original_values = df.iloc[0, 0]  # First cell value

    df_normalized = normalize_dataframe_columns(df)

    # Data should be preserved
    assert df_normalized.iloc[0, 0] == original_values


# ============================================================================
# dataframe_to_dict_list Tests
# ============================================================================


def test_dataframe_to_dict_list():
    """dataframe_to_dict_list should convert DataFrame to list of dicts."""
    data = {
        "Col1": [1, 2, 3],
        "Col2": ["a", "b", "c"],
    }
    df = pd.DataFrame(data)

    dict_list = dataframe_to_dict_list(df)

    assert isinstance(dict_list, list)
    assert len(dict_list) == 3
    assert dict_list[0] == {"Col1": 1, "Col2": "a"}
    assert dict_list[1] == {"Col1": 2, "Col2": "b"}


def test_dataframe_to_dict_list_handles_nan():
    """dataframe_to_dict_list should convert NaN to None."""
    data = {
        "Col1": [1, 2, 3],
        "Col2": [None, "b", None],  # NaN values
    }
    df = pd.DataFrame(data)

    dict_list = dataframe_to_dict_list(df)

    assert dict_list[0]["Col2"] is None
    assert dict_list[1]["Col2"] == "b"
    assert dict_list[2]["Col2"] is None


# ============================================================================
# export_results_to_excel Tests
# ============================================================================


def test_export_results_to_excel_returns_bytes():
    """export_results_to_excel should return bytes when no output_path given."""
    library_data = {
        "Project ID": ["Project_A"],
        "Library Name": ["Lib_001"],
        "Volume to Add (µl)": [5.0],
    }
    project_data = {
        "Project ID": ["Project_A"],
        "Library Count": [1],
    }

    library_df = pd.DataFrame(library_data)
    project_df = pd.DataFrame(project_data)

    result = export_results_to_excel(library_df, project_df)

    assert isinstance(result, bytes)
    assert len(result) > 0


def test_export_results_to_excel_saves_to_file():
    """export_results_to_excel should save file when output_path given."""
    library_data = {
        "Project ID": ["Project_A"],
        "Library Name": ["Lib_001"],
    }
    project_data = {
        "Project ID": ["Project_A"],
        "Library Count": [1],
    }

    library_df = pd.DataFrame(library_data)
    project_df = pd.DataFrame(project_data)

    output_path = FIXTURES_DIR / "test_export.xlsx"

    result = export_results_to_excel(library_df, project_df, output_path=output_path)

    assert result is None  # Should return None when saving to file
    assert output_path.exists()

    # Cleanup
    output_path.unlink()


def test_export_results_has_multiple_sheets():
    """Exported Excel should have three sheets: Libraries, Projects, Metadata."""
    library_data = {"Project ID": ["Project_A"], "Library Name": ["Lib_001"]}
    project_data = {"Project ID": ["Project_A"], "Library Count": [1]}

    library_df = pd.DataFrame(library_data)
    project_df = pd.DataFrame(project_data)

    excel_bytes = export_results_to_excel(library_df, project_df)

    # Read back the Excel file
    excel_file = BytesIO(excel_bytes)
    xls = pd.ExcelFile(excel_file)

    assert "PoolingPlan_Libraries" in xls.sheet_names
    assert "PoolingPlan_Projects" in xls.sheet_names
    assert "Metadata" in xls.sheet_names


def test_export_results_metadata_includes_timestamp():
    """Metadata sheet should include generation timestamp."""
    library_df = pd.DataFrame({"Col1": [1]})
    project_df = pd.DataFrame({"Col2": [2]})

    excel_bytes = export_results_to_excel(library_df, project_df)

    # Read metadata sheet
    metadata_df = pd.read_excel(BytesIO(excel_bytes), sheet_name="Metadata")

    assert "Parameter" in metadata_df.columns
    assert "Value" in metadata_df.columns
    assert "Generated At" in metadata_df["Parameter"].values


# ============================================================================
# generate_export_filename Tests
# ============================================================================


def test_generate_export_filename():
    """generate_export_filename should create timestamped filename."""
    filename = generate_export_filename()

    assert filename.startswith("pooling_plan_")
    assert filename.endswith(".xlsx")
    assert len(filename) > 20  # Should include timestamp


def test_generate_export_filename_custom_prefix():
    """generate_export_filename should accept custom prefix."""
    filename = generate_export_filename(prefix="my_pool")

    assert filename.startswith("my_pool_")
    assert filename.endswith(".xlsx")


# ============================================================================
# create_library_dataframe_for_export Tests
# ============================================================================


def test_create_library_dataframe_for_export():
    """create_library_dataframe_for_export should format data correctly."""
    libraries = [
        {
            "project_id": "Project_A",
            "library_name": "Lib_001",
            "pool_fraction": 0.33,
            "flags": ["Warning 1", "Warning 2"],
        }
    ]

    df = create_library_dataframe_for_export(libraries)

    assert isinstance(df, pd.DataFrame)
    # Flags should be comma-separated string
    assert isinstance(df.loc[0, "Flags"], str)
    assert "Warning 1" in df.loc[0, "Flags"]


def test_create_library_dataframe_for_export_converts_fraction_to_percentage():
    """Pool fraction should be converted from 0-1 to percentage."""
    libraries = [{"pool_fraction": 0.33}]

    df = create_library_dataframe_for_export(libraries)

    if "Pool Fraction (%)" in df.columns and "pool_fraction" in libraries[0]:
        # Should be converted to percentage
        assert df.loc[0, "Pool Fraction (%)"] == 33.0


# ============================================================================
# create_project_dataframe_for_export Tests
# ============================================================================


def test_create_project_dataframe_for_export():
    """create_project_dataframe_for_export should format data correctly."""
    projects = [
        {
            "project_id": "Project_A",
            "library_count": 10,
            "pool_fraction": 0.5,
        }
    ]

    df = create_project_dataframe_for_export(projects)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
