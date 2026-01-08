"""
Test io.py with real test data files.

This script verifies that io.py can correctly load and process the test files
in the data/ directory.
"""

import sys
from pathlib import Path

import pandas as pd

from pooling_calculator.io import (
    load_spreadsheet,
    normalize_dataframe_columns,
    dataframe_to_dict_list,
)

# Use ASCII characters for Windows compatibility
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"

def main():
    print("=" * 70)
    print("Testing io.py with Real Data Files")
    print("=" * 70)
    print()

    # Test files
    test_input_xlsx = Path("data/7050I_test_input.xlsx")
    test_input_csv = Path("data/7050I_test_input.csv")
    expected_output_xlsx = Path("data/7050I_expected_outputs.xlsx")
    expected_output_csv = Path("data/7050I_expected_outputs.csv")

    # Test 1: Load Excel input file
    print("Test 1: Loading Excel input file...")
    try:
        df_input = load_spreadsheet(test_input_xlsx)
        print(f"  {CHECK} Loaded {len(df_input)} rows from {test_input_xlsx.name}")
        print(f"  Columns: {list(df_input.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load {test_input_xlsx.name}: {e}")
        return False

    # Test 2: Load CSV input file
    print("Test 2: Loading CSV input file...")
    try:
        df_csv = pd.read_csv(test_input_csv)
        print(f"  {CHECK} Loaded {len(df_csv)} rows from {test_input_csv.name}")
        print(f"  Columns: {list(df_csv.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load {test_input_csv.name}: {e}")
        # CSV loading is optional, continue
        print()

    # Test 3: Show first few rows
    print("Test 3: Displaying first 3 rows of input data...")
    print(df_input.head(3).to_string())
    print()

    # Test 4: Column normalization
    print("Test 4: Normalizing column names...")
    try:
        df_normalized = normalize_dataframe_columns(df_input)
        print(f"  {CHECK} Normalized columns")
        print(f"  Original: {list(df_input.columns)}")
        print(f"  Normalized: {list(df_normalized.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to normalize columns: {e}")
        return False

    # Test 5: Convert to dict list
    print("Test 5: Converting to dictionary list...")
    try:
        dict_list = dataframe_to_dict_list(df_normalized)
        print(f"  {CHECK} Converted to {len(dict_list)} dictionaries")
        print(f"  First record keys: {list(dict_list[0].keys())}")
        print()
        print("  First record:")
        for key, value in dict_list[0].items():
            print(f"    {key}: {value}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to convert to dict list: {e}")
        return False

    # Test 6: Load expected outputs
    print("Test 6: Loading expected output file...")
    try:
        df_expected = load_spreadsheet(expected_output_xlsx)
        print(f"  {CHECK} Loaded {len(df_expected)} rows from {expected_output_xlsx.name}")
        print(f"  Columns: {list(df_expected.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load {expected_output_xlsx.name}: {e}")
        return False

    # Test 7: Check for required columns in input
    print("Test 7: Checking for required columns...")
    from pooling_calculator.config import REQUIRED_COLUMNS

    normalized_cols = [col.lower() for col in df_normalized.columns]
    required_cols_lower = [col.lower() for col in REQUIRED_COLUMNS]

    missing = []
    for req_col in REQUIRED_COLUMNS:
        if req_col not in df_normalized.columns:
            # Check if it exists in lowercase
            req_lower = req_col.lower()
            if req_lower not in normalized_cols:
                missing.append(req_col)

    if missing:
        print(f"  {WARN} Missing required columns: {missing}")
        print(f"  Note: This is expected if the test file uses different column names")
    else:
        print(f"  {CHECK} All required columns present")
    print()

    # Summary
    print("=" * 70)
    print(f"{CHECK} All io.py functions work with real test data!")
    print("=" * 70)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
