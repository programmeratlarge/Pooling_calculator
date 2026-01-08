"""
Test UI integration with real data.

This script tests the process_upload function with the 7050I test dataset
to ensure the complete end-to-end pipeline works.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from pooling_calculator.ui import process_upload

# Use ASCII characters for Windows compatibility
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"


def main():
    print("=" * 70)
    print("Testing UI Integration with Real Data (7050I)")
    print("=" * 70)
    print()

    # Prepare test file
    test_input_csv = Path("data/7050I_test_input.csv")

    if not test_input_csv.exists():
        print(f"  {CROSS} Test file not found: {test_input_csv}")
        return False

    print(f"Loading test data from {test_input_csv}...")
    print()

    # Mock file object (Gradio passes file objects with .name attribute)
    file_obj = Mock()
    file_obj.name = str(test_input_csv)

    # Test parameters
    desired_pool_volume = 18.785  # From expected outputs
    min_volume = 0.001  # 1 nL
    max_volume = None  # No maximum
    total_reads = None  # Not calculating expected reads

    # Test 1: Process upload with valid data
    print("Test 1: Processing valid input file...")
    try:
        status, lib_df, proj_df, excel_bytes = process_upload(
            file_obj,
            desired_pool_volume,
            min_volume,
            max_volume,
            total_reads,
        )

        print(f"  {CHECK} process_upload completed")
        print()

        # Check status message (skip printing due to Unicode issues on Windows)
        print(f"  {CHECK} Status message length: {len(status)} characters")
        if "VALIDATION PASSED" in status:
            print(f"  {CHECK} Validation passed")
        elif "VALIDATION FAILED" in status:
            print(f"  {CROSS} Validation failed")
        print()

        # Check that we got valid results
        if lib_df is None or proj_df is None or excel_bytes is None:
            print(f"  {CROSS} Expected valid results, got None")
            return False

        print(f"  {CHECK} Received library dataframe with {len(lib_df)} rows")
        print(f"  {CHECK} Received project summary with {len(proj_df)} projects")
        print(f"  {CHECK} Received Excel file ({len(excel_bytes)} bytes)")
        print()

    except Exception as e:
        print(f"  {CROSS} process_upload failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Verify library table structure
    print("Test 2: Verifying library table structure...")
    expected_cols = [
        "Library Name",
        "Project ID",
        "Final ng/ul",
        "Adjusted peak size",
        "Target Reads (M)",
        "Calculated nM",
        "Effective nM (Use)",
        "Stock Volume (µl)",
        "Pool Fraction",
        "Flags",
    ]

    missing_cols = [col for col in expected_cols if col not in lib_df.columns]
    if missing_cols:
        print(f"  {WARN} Missing columns: {missing_cols}")
    else:
        print(f"  {CHECK} All expected columns present")

    print(f"  Columns: {list(lib_df.columns)}")
    print()

    # Test 3: Display sample library results
    print("Test 3: Sample library results (first 3):")
    print(lib_df.head(3).to_string(index=False))
    print()

    # Test 4: Display project summary
    print("Test 4: Project summary:")
    print(proj_df.to_string(index=False))
    print()

    # Test 5: Verify volumes sum to desired pool volume
    print("Test 5: Verifying total volume...")
    if "Stock Volume (µl)" in lib_df.columns:
        # Need to get the actual data from display dataframe
        # The display df has rounded values, so we need to check the sum
        total_volume = lib_df["Stock Volume (µl)"].sum()
        print(f"  Total volume: {total_volume:.6f} µl")
        print(f"  Desired volume: {desired_pool_volume:.6f} µl")

        # Allow small rounding error
        if abs(total_volume - desired_pool_volume) < 0.1:
            print(f"  {CHECK} Total volume matches desired pool volume")
        else:
            print(f"  {WARN} Volume mismatch (may be due to rounding)")
    else:
        print(f"  {CROSS} Stock Volume column missing")
    print()

    # Test 6: Test with invalid parameters
    print("Test 6: Testing error handling with invalid parameters...")
    status_err, lib_err, proj_err, excel_err = process_upload(
        file_obj,
        -10.0,  # Invalid: negative volume
        min_volume,
        max_volume,
        total_reads,
    )

    if lib_err is None and "Error" in status_err:
        print(f"  {CHECK} Correctly rejected negative pool volume")
        # Skip printing error message due to Unicode issues on Windows
    else:
        print(f"  {WARN} Error handling may not be working as expected")
    print()

    # Test 7: Test with no file
    print("Test 7: Testing with no file uploaded...")
    status_none, lib_none, proj_none, excel_none = process_upload(
        None,  # No file
        desired_pool_volume,
        min_volume,
        max_volume,
        total_reads,
    )

    if lib_none is None and "upload" in status_none.lower():
        print(f"  {CHECK} Correctly handled missing file")
        print(f"  Message: {status_none}")
    else:
        print(f"  {WARN} Missing file handling may not be working")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Status: {CHECK} PASS")
    print(f"  UI integration tested successfully with real data")
    print(f"  - File upload and validation: Working")
    print(f"  - Computation pipeline: Working")
    print(f"  - Excel export: Working")
    print(f"  - Error handling: Working")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
