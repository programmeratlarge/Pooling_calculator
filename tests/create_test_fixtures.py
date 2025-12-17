"""
Script to create test fixture Excel files for unit tests.

Run this to regenerate test fixtures if needed.
"""

import pandas as pd
from pathlib import Path


def create_valid_pool_fixture():
    """Create a valid test pool Excel file."""
    data = {
        "Project ID": ["Project_A", "Project_A", "Project_B", "Project_B", "Project_C"],
        "Library Name": ["Lib_001", "Lib_002", "Lib_003", "Lib_004", "Lib_005"],
        "Final ng/ul": [12.5, 8.3, 15.7, 10.2, 20.0],
        "Total Volume": [30.0, 25.0, 40.0, 35.0, 50.0],
        "Barcodes": ["ATCG-GGTA", "GCTA-ATCG", "TTAA-CCGG", "GGCC-TTAA", "ACGT-TGCA"],
        "Adjusted peak size": [450.0, 380.0, 520.0, 410.0, 480.0],
        "Empirical Library nM": [None, 35.2, None, None, 45.5],
        "Target Reads (M)": [10.0, 10.0, 20.0, 15.0, 10.0],
    }

    df = pd.DataFrame(data)
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    output_path = fixtures_dir / "valid_pool.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Created: {output_path}")


def create_missing_column_fixture():
    """Create a test file with a missing required column."""
    data = {
        "Project ID": ["Project_A", "Project_B"],
        "Library Name": ["Lib_001", "Lib_002"],
        "Final ng/ul": [12.5, 8.3],
        # Missing "Total Volume" column
        "Barcodes": ["ATCG-GGTA", "GCTA-ATCG"],
        "Adjusted peak size": [450.0, 380.0],
        "Target Reads (M)": [10.0, 10.0],
    }

    df = pd.DataFrame(data)
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    output_path = fixtures_dir / "missing_column.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Created: {output_path}")


def create_alternative_column_names_fixture():
    """Create a test file with alternative column names that should be normalized."""
    data = {
        "project": ["Project_A", "Project_B"],  # Alternative name
        "library": ["Lib_001", "Lib_002"],  # Alternative name
        "concentration": [12.5, 8.3],  # Alternative name
        "volume": [30.0, 25.0],  # Alternative name
        "barcode": ["ATCG-GGTA", "GCTA-ATCG"],  # Alternative name
        "fragment_size": [450.0, 380.0],  # Alternative name
        "reads": [10.0, 10.0],  # Alternative name
    }

    df = pd.DataFrame(data)
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    output_path = fixtures_dir / "alternative_columns.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Created: {output_path}")


if __name__ == "__main__":
    print("Creating test fixtures...")
    create_valid_pool_fixture()
    create_missing_column_fixture()
    create_alternative_column_names_fixture()
    print("Done!")
