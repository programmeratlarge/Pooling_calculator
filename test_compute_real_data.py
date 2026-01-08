"""
Test computation engine with real 7050I test data.

This script verifies that compute.py correctly calculates:
- Molarity from concentration and fragment size
- Volumes for weighted pooling
- Project-level aggregation

Results should match 7050I_expected_outputs.csv.
"""

import sys
from pathlib import Path

import pandas as pd

from pooling_calculator.io import normalize_dataframe_columns
from pooling_calculator.compute import (
    compute_effective_molarity,
    compute_pool_volumes,
    summarize_by_project,
)

# Use ASCII characters for Windows compatibility
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"


def main():
    print("=" * 70)
    print("Testing Computation Engine with Real Data (7050I)")
    print("=" * 70)
    print()

    # Load test input
    test_input_csv = Path("data/7050I_test_input.csv")
    expected_output_csv = Path("data/7050I_expected_outputs.csv")

    print(f"Loading test input from {test_input_csv}...")
    try:
        df = pd.read_csv(test_input_csv)
        df_normalized = normalize_dataframe_columns(df)
        print(f"  {CHECK} Loaded {len(df_normalized)} libraries")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load: {e}")
        return False

    # Load expected outputs
    print(f"Loading expected outputs from {expected_output_csv}...")
    try:
        df_expected = pd.read_csv(expected_output_csv)
        print(f"  {CHECK} Loaded {len(df_expected)} expected results")
        print()
    except Exception as e:
        print(f"  {CROSS} Failed to load: {e}")
        return False

    # Step 1: Compute effective molarity
    print("Step 1: Computing effective molarity...")
    try:
        df_with_molarity = compute_effective_molarity(df_normalized)
        print(f"  {CHECK} Molarity calculated for all libraries")
        print()
    except Exception as e:
        print(f"  {CROSS} Molarity calculation failed: {e}")
        return False

    # Step 2: Verify molarity matches expected
    print("Step 2: Verifying molarity calculations...")
    molarity_errors = []
    for idx, row in df_with_molarity.iterrows():
        lib_name = row["Library Name"]
        calculated = row["Calculated nM"]
        expected_row = df_expected[df_expected["Library Name"] == lib_name]
        if len(expected_row) == 0:
            molarity_errors.append(f"Library {lib_name} not found in expected outputs")
            continue

        expected = expected_row["Calculated nM"].iloc[0]
        rel_error = abs(calculated - expected) / expected

        if rel_error > 0.001:  # 0.1% tolerance
            molarity_errors.append(
                f"Library {lib_name}: calculated={calculated:.6f} nM, "
                f"expected={expected:.6f} nM, error={rel_error:.4%}"
            )

    if molarity_errors:
        print(f"  {WARN} Molarity verification failed:")
        for err in molarity_errors:
            print(f"    - {err}")
        print()
    else:
        print(f"  {CHECK} All molarity values match expected (within 0.1%)")
        print()

    # Step 3: Compute pool volumes
    # From data/README.md: total expected volume sum is 18.785 µl
    expected_total_volume = df_expected["Stock Volume (µl)"].sum()
    print(f"Step 3: Computing pool volumes (target: {expected_total_volume:.3f} µl)...")
    try:
        df_with_volumes = compute_pool_volumes(
            df_with_molarity,
            desired_pool_volume_ul=expected_total_volume
        )
        print(f"  {CHECK} Volumes calculated for all libraries")
        print()
    except Exception as e:
        print(f"  {CROSS} Volume calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Verify volumes match expected
    print("Step 4: Verifying volume calculations...")
    volume_errors = []
    for idx, row in df_with_volumes.iterrows():
        lib_name = row["Library Name"]
        calculated = row["Stock Volume (µl)"]
        expected_row = df_expected[df_expected["Library Name"] == lib_name]
        if len(expected_row) == 0:
            volume_errors.append(f"Library {lib_name} not found in expected outputs")
            continue

        expected = expected_row["Stock Volume (µl)"].iloc[0]
        rel_error = abs(calculated - expected) / expected if expected > 0 else 0

        if rel_error > 0.01:  # 1% tolerance (more lenient for small volumes)
            volume_errors.append(
                f"Library {lib_name}: calculated={calculated:.6f} µl, "
                f"expected={expected:.6f} µl, error={rel_error:.4%}"
            )

    if volume_errors:
        print(f"  {WARN} Volume verification failed:")
        for err in volume_errors:
            print(f"    - {err}")
        print()
    else:
        print(f"  {CHECK} All volumes match expected (within 1%)")
        print()

    # Step 5: Verify total volume
    total_calculated = df_with_volumes["Stock Volume (µl)"].sum()
    total_expected = expected_total_volume
    print(f"Step 5: Verifying total volume...")
    print(f"  Calculated: {total_calculated:.6f} µl")
    print(f"  Expected: {total_expected:.6f} µl")
    print(f"  Difference: {abs(total_calculated - total_expected):.9f} µl")

    if abs(total_calculated - total_expected) < 1e-6:
        print(f"  {CHECK} Total volume matches expected")
    else:
        print(f"  {WARN} Total volume mismatch (should be negligible)")
    print()

    # Step 6: Project aggregation
    print("Step 6: Testing project aggregation...")
    try:
        df_projects = summarize_by_project(df_with_volumes)
        print(f"  {CHECK} Project summary created")
        print(f"  Number of projects: {len(df_projects)}")
        print()
        print("Project Summary:")
        print(df_projects.to_string(index=False))
        print()
    except Exception as e:
        print(f"  {CROSS} Project aggregation failed: {e}")
        return False

    # Step 7: Display sample results
    print("Step 7: Sample library results (first 5):")
    print()
    display_cols = [
        "Library Name",
        "Final ng/ul",
        "Adjusted peak size",
        "Target Reads (M)",
        "Calculated nM",
        "Stock Volume (µl)",
    ]
    print(df_with_volumes[display_cols].head(5).to_string(index=False))
    print()

    # Step 8: Check for flags
    print("Step 8: Checking for flags...")
    flagged = df_with_volumes[df_with_volumes["Flags"] != ""]
    if len(flagged) > 0:
        print(f"  {WARN} {len(flagged)} libraries have flags:")
        for idx, row in flagged.iterrows():
            print(f"    - {row['Library Name']}: {row['Flags']}")
    else:
        print(f"  {CHECK} No flags raised (all volumes valid)")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Libraries processed: {len(df_with_volumes)}")
    print(f"  Molarity errors: {len(molarity_errors)}")
    print(f"  Volume errors: {len(volume_errors)}")
    print(f"  Total volume: {total_calculated:.6f} µl")
    print(f"  Flags raised: {len(flagged)}")

    success = len(molarity_errors) == 0 and len(volume_errors) == 0

    if success:
        print(f"  Status: {CHECK} PASS")
    else:
        print(f"  Status: {CROSS} FAIL")

    print("=" * 70)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
