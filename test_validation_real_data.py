"""
Test validation module with real data files.

Validates the 7050I test dataset to ensure the validation module
correctly identifies any issues.
"""

import sys
from pathlib import Path

import pandas as pd

from pooling_calculator.io import normalize_dataframe_columns
from pooling_calculator.validation import run_all_validations

# Use ASCII characters for Windows compatibility
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"


def main():
    print("=" * 70)
    print("Testing Validation Module with Real Data Files")
    print("=" * 70)
    print()

    # Load the CSV file (easier to work with than Excel with title rows)
    test_input_csv = Path("data/7050I_test_input.csv")

    print(f"Loading test data from {test_input_csv}...")
    try:
        df = pd.read_csv(test_input_csv)
        print(f"  {CHECK} Loaded {len(df)} libraries")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load: {e}")
        return False

    # Normalize column names
    print("Normalizing column names...")
    df_normalized = normalize_dataframe_columns(df)
    print(f"  {CHECK} Columns normalized")
    print(f"  Columns: {list(df_normalized.columns)}")
    print()

    # Run all validations
    print("Running validation checks...")
    result = run_all_validations(df_normalized)
    print()

    # Display results
    print("=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print()

    if result.is_valid:
        print(f"{CHECK} DATA IS VALID")
        print()
    else:
        print(f"{CROSS} DATA HAS ERRORS")
        print()

    # Show errors
    if result.errors:
        print(f"ERRORS ({len(result.errors)}):")
        for i, error in enumerate(result.errors, 1):
            print(f"  {i}. {error}")
        print()
    else:
        print(f"{CHECK} No errors found")
        print()

    # Show warnings
    if result.warnings:
        print(f"WARNINGS ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")
        print()
    else:
        print(f"{CHECK} No warnings")
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Libraries checked: {len(df_normalized)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")
    print(f"  Status: {'PASS' if result.is_valid else 'FAIL'}")
    print("=" * 70)

    # Show sample data
    if result.is_valid:
        print()
        print("Sample of validated data (first 3 rows):")
        print(df_normalized.head(3).to_string())

    return result.is_valid


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
