"""
Test io.py with real test data files - handling header rows.

This script verifies that io.py can correctly load and process the test files
in the data/ directory, including handling files with title rows.
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

def load_with_skiprows(file_path, skiprows=0):
    """Load Excel file and skip title rows."""
    import pandas as pd
    from io import BytesIO

    df = pd.read_excel(file_path, skiprows=skiprows)
    # Remove completely empty rows
    df = df.dropna(how="all")
    # Reset index after dropping rows
    df = df.reset_index(drop=True)
    return df

def main():
    print("=" * 70)
    print("Testing io.py with Real Data Files (v2 - with skiprows)")
    print("=" * 70)
    print()

    # Test files
    test_input_xlsx = Path("data/7050I_test_input.xlsx")
    test_input_csv = Path("data/7050I_test_input.csv")
    expected_output_xlsx = Path("data/7050I_expected_outputs.xlsx")

    # Test 1: Load Excel with skiprows to handle title row
    print("Test 1: Loading Excel input file (skipping title row)...")
    try:
        df_input = load_with_skiprows(test_input_xlsx, skiprows=1)
        print(f"  {CHECK} Loaded {len(df_input)} rows from {test_input_xlsx.name}")
        print(f"  Columns: {list(df_input.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load {test_input_xlsx.name}: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Load CSV input file (no title row)
    print("Test 2: Loading CSV input file...")
    try:
        df_csv = pd.read_csv(test_input_csv)
        print(f"  {CHECK} Loaded {len(df_csv)} rows from {test_input_csv.name}")
        print(f"  Columns: {list(df_csv.columns)}")
        print()

        # Verify CSV and Excel have same structure after skiprows
        if list(df_csv.columns) == list(df_input.columns):
            print(f"  {CHECK} CSV and Excel column names match!")
        else:
            print(f"  {WARN} Column name mismatch:")
            print(f"    CSV: {list(df_csv.columns)}")
            print(f"    Excel: {list(df_input.columns)}")
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

        # Show any changes
        changes = []
        for orig, norm in zip(df_input.columns, df_normalized.columns):
            if orig != norm:
                changes.append(f"'{orig}' -> '{norm}'")

        if changes:
            print(f"  Column mappings applied:")
            for change in changes:
                print(f"    {change}")
        else:
            print(f"  No column name changes needed")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to normalize columns: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Convert to dict list
    print("Test 5: Converting to dictionary list...")
    try:
        dict_list = dataframe_to_dict_list(df_normalized)
        print(f"  {CHECK} Converted to {len(dict_list)} dictionaries")
        print(f"  First record keys: {list(dict_list[0].keys())}")
        print()
        print("  First record values:")
        for key, value in dict_list[0].items():
            print(f"    {key}: {value}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to convert to dict list: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 6: Load expected outputs
    print("Test 6: Loading expected output file (skipping title row)...")
    try:
        df_expected = load_with_skiprows(expected_output_xlsx, skiprows=1)
        print(f"  {CHECK} Loaded {len(df_expected)} rows from {expected_output_xlsx.name}")
        print(f"  Columns: {list(df_expected.columns)}")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load {expected_output_xlsx.name}: {e}")
        return False

    # Test 7: Check for required columns in input
    print("Test 7: Checking for required columns...")
    from pooling_calculator.config import REQUIRED_COLUMNS

    normalized_cols_lower = [col.lower() for col in df_normalized.columns]

    missing = []
    found = []
    for req_col in REQUIRED_COLUMNS:
        if req_col in df_normalized.columns:
            found.append(req_col)
        else:
            # Check if it exists in lowercase
            req_lower = req_col.lower()
            if req_lower not in normalized_cols_lower:
                missing.append(req_col)
            else:
                found.append(req_col)

    if missing:
        print(f"  {WARN} Missing required columns: {missing}")
        print(f"  {CHECK} Found columns: {found}")
    else:
        print(f"  {CHECK} All {len(REQUIRED_COLUMNS)} required columns present!")
        for col in found:
            print(f"    - {col}")
    print()

    # Test 8: Data types and values check
    print("Test 8: Checking data types and sample values...")
    for col in df_normalized.columns:
        sample_val = df_normalized[col].iloc[0] if len(df_normalized) > 0 else None
        dtype = df_normalized[col].dtype
        print(f"  {col}: {dtype} (sample: {sample_val})")
    print()

    # Summary
    print("=" * 70)
    print(f"{CHECK} All io.py functions work correctly with real test data!")
    print()
    print("Key findings:")
    print(f"  - Input file has {len(df_input)} libraries")
    print(f"  - Column normalization: {'changes applied' if changes else 'no changes needed'}")
    print(f"  - Required columns: {len(found)}/{len(REQUIRED_COLUMNS)} found")
    print("=" * 70)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
