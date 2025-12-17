"""
Validation logic for Pooling Calculator.

This module handles validation of input data including:
- Column presence checks
- Row-level data validation (types, constraints)
- Uniqueness checks (Library Name, Barcodes)
- Comprehensive error and warning messages
"""

import pandas as pd

from pooling_calculator.config import (
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    MIN_CONCENTRATION_NG_UL,
    WARN_LOW_CONCENTRATION_NG_UL,
    WARN_HIGH_CONCENTRATION_NG_UL,
    MIN_FRAGMENT_SIZE_BP,
    WARN_LOW_FRAGMENT_SIZE_BP,
    WARN_HIGH_FRAGMENT_SIZE_BP,
    MIN_TOTAL_VOLUME_UL,
    WARN_LOW_TOTAL_VOLUME_UL,
    MIN_MOLARITY_NM,
    WARN_LOW_MOLARITY_NM,
    WARN_HIGH_MOLARITY_NM,
    MIN_TARGET_READS_M,
    ERROR_MISSING_COLUMN,
    ERROR_NEGATIVE_VALUE,
    ERROR_INVALID_TYPE,
    ERROR_DUPLICATE_VALUE,
    ERROR_EMPTY_VALUE,
    WARN_LOW_CONCENTRATION,
    WARN_HIGH_CONCENTRATION,
    WARN_LOW_VOLUME,
)
from pooling_calculator.models import ValidationResult


def validate_columns(df: pd.DataFrame) -> list[str]:
    """
    Validate that all required columns are present.

    Args:
        df: DataFrame with column names to check

    Returns:
        List of error messages (empty if all columns present)
    """
    errors = []

    # Check for required columns (case-insensitive)
    df_cols_lower = [col.lower() for col in df.columns]

    for req_col in REQUIRED_COLUMNS:
        req_col_lower = req_col.lower()
        if req_col not in df.columns and req_col_lower not in df_cols_lower:
            errors.append(ERROR_MISSING_COLUMN.format(column=req_col))

    return errors


def validate_row_data_types(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """
    Validate data types and basic constraints for each row.

    Args:
        df: DataFrame with normalized column names

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    for idx, row in df.iterrows():
        row_num = idx + 1  # Human-readable row number (1-indexed)

        # Check Project ID
        if "Project ID" in df.columns:
            val = row["Project ID"]
            if pd.isna(val) or str(val).strip() == "":
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Project ID"))

        # Check Library Name
        if "Library Name" in df.columns:
            val = row["Library Name"]
            if pd.isna(val) or str(val).strip() == "":
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Library Name"))

        # Check Final ng/ul (concentration)
        if "Final ng/ul" in df.columns:
            val = row["Final ng/ul"]
            if pd.isna(val):
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Final ng/ul"))
            else:
                try:
                    conc = float(val)
                    if conc <= 0:
                        errors.append(ERROR_NEGATIVE_VALUE.format(
                            row=row_num, column="Final ng/ul", value=conc
                        ))
                    elif conc < MIN_CONCENTRATION_NG_UL:
                        errors.append(f"Row {row_num}, Final ng/ul: Concentration too low ({conc:.3f} ng/µl < {MIN_CONCENTRATION_NG_UL} ng/µl)")
                    elif conc < WARN_LOW_CONCENTRATION_NG_UL:
                        warnings.append(WARN_LOW_CONCENTRATION.format(row=row_num, value=conc))
                    elif conc > WARN_HIGH_CONCENTRATION_NG_UL:
                        warnings.append(WARN_HIGH_CONCENTRATION.format(row=row_num, value=conc))
                except (ValueError, TypeError):
                    errors.append(ERROR_INVALID_TYPE.format(
                        row=row_num, column="Final ng/ul", dtype="number", value=val
                    ))

        # Check Total Volume
        if "Total Volume" in df.columns:
            val = row["Total Volume"]
            if pd.isna(val):
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Total Volume"))
            else:
                try:
                    vol = float(val)
                    if vol <= 0:
                        errors.append(ERROR_NEGATIVE_VALUE.format(
                            row=row_num, column="Total Volume", value=vol
                        ))
                    elif vol < MIN_TOTAL_VOLUME_UL:
                        errors.append(f"Row {row_num}, Total Volume: Volume too low ({vol:.2f} µl < {MIN_TOTAL_VOLUME_UL} µl)")
                    elif vol < WARN_LOW_TOTAL_VOLUME_UL:
                        warnings.append(WARN_LOW_VOLUME.format(row=row_num, value=vol))
                except (ValueError, TypeError):
                    errors.append(ERROR_INVALID_TYPE.format(
                        row=row_num, column="Total Volume", dtype="number", value=val
                    ))

        # Check Barcodes
        if "Barcodes" in df.columns:
            val = row["Barcodes"]
            if pd.isna(val) or str(val).strip() == "":
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Barcodes"))

        # Check Adjusted peak size
        if "Adjusted peak size" in df.columns:
            val = row["Adjusted peak size"]
            if pd.isna(val):
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Adjusted peak size"))
            else:
                try:
                    size = float(val)
                    if size <= 0:
                        errors.append(ERROR_NEGATIVE_VALUE.format(
                            row=row_num, column="Adjusted peak size", value=size
                        ))
                    elif size < MIN_FRAGMENT_SIZE_BP:
                        errors.append(f"Row {row_num}, Adjusted peak size: Fragment size too small ({size:.0f} bp < {MIN_FRAGMENT_SIZE_BP} bp)")
                    elif size < WARN_LOW_FRAGMENT_SIZE_BP:
                        warnings.append(f"Row {row_num}, Adjusted peak size: Unusually small fragment ({size:.0f} bp)")
                    elif size > WARN_HIGH_FRAGMENT_SIZE_BP:
                        warnings.append(f"Row {row_num}, Adjusted peak size: Unusually large fragment ({size:.0f} bp)")
                except (ValueError, TypeError):
                    errors.append(ERROR_INVALID_TYPE.format(
                        row=row_num, column="Adjusted peak size", dtype="number", value=val
                    ))

        # Check Empirical Library nM (optional, but if present must be valid)
        if "Empirical Library nM" in df.columns:
            val = row["Empirical Library nM"]
            if not pd.isna(val):  # Only validate if provided
                try:
                    molarity = float(val)
                    if molarity <= 0:
                        errors.append(ERROR_NEGATIVE_VALUE.format(
                            row=row_num, column="Empirical Library nM", value=molarity
                        ))
                    elif molarity < MIN_MOLARITY_NM:
                        errors.append(f"Row {row_num}, Empirical Library nM: Molarity too low ({molarity:.3f} nM < {MIN_MOLARITY_NM} nM)")
                    elif molarity < WARN_LOW_MOLARITY_NM:
                        warnings.append(f"Row {row_num}, Empirical Library nM: Very low molarity ({molarity:.3f} nM)")
                    elif molarity > WARN_HIGH_MOLARITY_NM:
                        warnings.append(f"Row {row_num}, Empirical Library nM: Very high molarity ({molarity:.1f} nM)")
                except (ValueError, TypeError):
                    errors.append(ERROR_INVALID_TYPE.format(
                        row=row_num, column="Empirical Library nM", dtype="number", value=val
                    ))

        # Check Target Reads (M)
        if "Target Reads (M)" in df.columns:
            val = row["Target Reads (M)"]
            if pd.isna(val):
                errors.append(ERROR_EMPTY_VALUE.format(row=row_num, column="Target Reads (M)"))
            else:
                try:
                    reads = float(val)
                    if reads <= 0:
                        errors.append(ERROR_NEGATIVE_VALUE.format(
                            row=row_num, column="Target Reads (M)", value=reads
                        ))
                    elif reads < MIN_TARGET_READS_M:
                        errors.append(f"Row {row_num}, Target Reads (M): Target reads too low ({reads:.2f} M < {MIN_TARGET_READS_M} M)")
                except (ValueError, TypeError):
                    errors.append(ERROR_INVALID_TYPE.format(
                        row=row_num, column="Target Reads (M)", dtype="number", value=val
                    ))

    return errors, warnings


def validate_uniqueness(df: pd.DataFrame) -> list[str]:
    """
    Check for duplicate values in columns that must be unique.

    Args:
        df: DataFrame with normalized column names

    Returns:
        List of error messages for duplicates
    """
    errors = []

    # Check Library Name uniqueness
    if "Library Name" in df.columns:
        lib_names = df["Library Name"].dropna()
        duplicates = lib_names[lib_names.duplicated()].unique()
        if len(duplicates) > 0:
            for dup in duplicates:
                # Find all rows with this duplicate
                dup_rows = df[df["Library Name"] == dup].index + 1
                errors.append(ERROR_DUPLICATE_VALUE.format(
                    column="Library Name",
                    value=dup,
                    rows=", ".join(map(str, dup_rows.tolist()))
                ))

    # Check Barcodes uniqueness
    if "Barcodes" in df.columns:
        barcodes = df["Barcodes"].dropna()
        duplicates = barcodes[barcodes.duplicated()].unique()
        if len(duplicates) > 0:
            for dup in duplicates:
                # Find all rows with this duplicate
                dup_rows = df[df["Barcodes"] == dup].index + 1
                errors.append(ERROR_DUPLICATE_VALUE.format(
                    column="Barcodes",
                    value=dup,
                    rows=", ".join(map(str, dup_rows.tolist()))
                ))

    return errors


def run_all_validations(df: pd.DataFrame) -> ValidationResult:
    """
    Run all validation checks on input DataFrame.

    Args:
        df: DataFrame with normalized column names

    Returns:
        ValidationResult with errors, warnings, and validity status
    """
    all_errors = []
    all_warnings = []

    # 1. Check column presence
    col_errors = validate_columns(df)
    all_errors.extend(col_errors)

    # If columns are missing, can't do further validation
    if col_errors:
        return ValidationResult(
            is_valid=False,
            errors=all_errors,
            warnings=all_warnings
        )

    # 2. Check row-level data
    row_errors, row_warnings = validate_row_data_types(df)
    all_errors.extend(row_errors)
    all_warnings.extend(row_warnings)

    # 3. Check uniqueness
    unique_errors = validate_uniqueness(df)
    all_errors.extend(unique_errors)

    # Determine validity
    is_valid = len(all_errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=all_errors,
        warnings=all_warnings
    )
