"""
Input/Output operations for Pooling Calculator.

This module handles reading spreadsheets and exporting results to Excel files.
"""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from pooling_calculator import __version__
from pooling_calculator.config import (
    DEFAULT_SHEET_NAME,
    OUTPUT_LIBRARY_COLUMNS,
    OUTPUT_PROJECT_COLUMNS,
    normalize_column_name,
)


def load_spreadsheet(
    file_path_or_bytes: str | Path | bytes | BinaryIO,
    sheet_name: str | int | None = DEFAULT_SHEET_NAME,
) -> pd.DataFrame:
    """
    Load a spreadsheet from file path or bytes.

    Args:
        file_path_or_bytes: Path to Excel file, bytes, or file-like object
        sheet_name: Sheet name or index to read (None = first sheet, 0 = first sheet by index)

    Returns:
        DataFrame with raw data from spreadsheet

    Raises:
        FileNotFoundError: If file path doesn't exist
        ValueError: If file format is unsupported or corrupted
    """
    try:
        # If sheet_name is None, read first sheet by using 0 instead
        # (pandas returns dict when sheet_name=None)
        if sheet_name is None:
            sheet_name = 0

        # Handle different input types
        if isinstance(file_path_or_bytes, (str, Path)):
            file_path = Path(file_path_or_bytes)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Detect file type by extension
            if file_path.suffix.lower() == ".csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
        elif isinstance(file_path_or_bytes, bytes):
            df = pd.read_excel(BytesIO(file_path_or_bytes), sheet_name=sheet_name)
        else:
            # Assume it's a file-like object
            df = pd.read_excel(file_path_or_bytes, sheet_name=sheet_name)

        # Remove completely empty rows
        df = df.dropna(how="all")

        # Reset index after dropping rows
        df = df.reset_index(drop=True)

        return df

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {e}") from e


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names in DataFrame using config mappings.

    Args:
        df: DataFrame with raw column names

    Returns:
        DataFrame with normalized column names
    """
    # Create a mapping of original → normalized names
    column_mapping = {}
    for col in df.columns:
        normalized = normalize_column_name(str(col))
        column_mapping[col] = normalized

    # Rename columns
    df_normalized = df.rename(columns=column_mapping)

    return df_normalized


def dataframe_to_dict_list(df: pd.DataFrame) -> list[dict]:
    """
    Convert DataFrame to list of dictionaries for model creation.

    Args:
        df: DataFrame with library data

    Returns:
        List of dictionaries, one per row
    """
    # Convert to dict, handling NaN values
    records = df.to_dict(orient="records")

    # Replace NaN with None for optional fields
    cleaned_records = []
    for record in records:
        cleaned = {}
        for key, value in record.items():
            # Check for NaN using pandas
            if pd.isna(value):
                cleaned[key] = None
            else:
                cleaned[key] = value
        cleaned_records.append(cleaned)

    return cleaned_records


def export_results_to_excel(
    library_df: pd.DataFrame,
    project_df: pd.DataFrame,
    output_path: str | Path | None = None,
    pooling_params: dict | None = None,
) -> bytes | None:
    """
    Export pooling results to Excel file with multiple sheets.

    Args:
        library_df: DataFrame with per-library results
        project_df: DataFrame with per-project summary
        output_path: Optional path to save file (if None, returns bytes)
        pooling_params: Optional dictionary of pooling parameters for metadata

    Returns:
        Bytes of Excel file if output_path is None, otherwise None
    """
    # Create BytesIO buffer or use file path
    if output_path is None:
        buffer = BytesIO()
        writer_target = buffer
    else:
        writer_target = Path(output_path)

    # Create Excel writer
    with pd.ExcelWriter(writer_target, engine="openpyxl") as writer:
        # Write library-level results
        library_df.to_excel(
            writer, sheet_name="PoolingPlan_Libraries", index=False, freeze_panes=(1, 0)
        )

        # Write project-level summary
        project_df.to_excel(
            writer, sheet_name="PoolingPlan_Projects", index=False, freeze_panes=(1, 0)
        )

        # Write metadata sheet
        metadata = _create_metadata_dict(pooling_params)
        metadata_df = pd.DataFrame(list(metadata.items()), columns=["Parameter", "Value"])
        metadata_df.to_excel(writer, sheet_name="Metadata", index=False, freeze_panes=(1, 0))

        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            _auto_adjust_column_widths(worksheet)

    # Return bytes if no output path specified
    if output_path is None:
        buffer.seek(0)
        return buffer.getvalue()
    else:
        return None


def generate_export_filename(prefix: str = "pooling_plan") -> str:
    """
    Generate a timestamped filename for exports.

    Args:
        prefix: Prefix for filename

    Returns:
        Filename string with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.xlsx"


def _create_metadata_dict(pooling_params: dict | None = None) -> dict[str, str]:
    """
    Create metadata dictionary for export.

    Args:
        pooling_params: Optional pooling parameters

    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {
        "Generated At": datetime.now().isoformat(),
        "App Name": "Pooling Calculator",
        "App Version": __version__,
    }

    # Add pooling parameters if provided
    if pooling_params:
        metadata["Total Pool Volume (µl)"] = str(pooling_params.get("desired_total_volume_ul", "N/A"))
        metadata["Minimum Volume (µl)"] = str(pooling_params.get("min_volume_ul", "N/A"))

        max_vol = pooling_params.get("max_volume_ul")
        metadata["Maximum Volume (µl)"] = str(max_vol) if max_vol is not None else "None"

        total_reads = pooling_params.get("total_reads_m")
        metadata["Total Reads (M)"] = str(total_reads) if total_reads is not None else "None"

    return metadata


def _auto_adjust_column_widths(worksheet) -> None:
    """
    Auto-adjust column widths in an openpyxl worksheet.

    Args:
        worksheet: openpyxl worksheet object
    """
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter

        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        # Set width with some padding
        adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
        worksheet.column_dimensions[column_letter].width = adjusted_width


def create_library_dataframe_for_export(libraries: list[dict]) -> pd.DataFrame:
    """
    Create a properly formatted DataFrame for library export.

    Args:
        libraries: List of library dictionaries with computed fields

    Returns:
        DataFrame with standardized columns and formatting
    """
    df = pd.DataFrame(libraries)

    # Format pool fraction BEFORE reordering (while pool_fraction column still exists)
    if "pool_fraction" in df.columns:
        df["Pool Fraction (%)"] = df["pool_fraction"] * 100

    # Format flags column (convert list to comma-separated string) - handle both lowercase and title case
    if "flags" in df.columns:
        df["Flags"] = df["flags"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else (str(x) if x is not None else "")
        )
    elif "Flags" in df.columns:
        df["Flags"] = df["Flags"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else (str(x) if x is not None else "")
        )

    # Ensure we have all expected columns (add missing ones as NaN)
    for col in OUTPUT_LIBRARY_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Reorder columns to match expected output
    df = df[OUTPUT_LIBRARY_COLUMNS]

    return df


def create_project_dataframe_for_export(projects: list[dict]) -> pd.DataFrame:
    """
    Create a properly formatted DataFrame for project export.

    Args:
        projects: List of project summary dictionaries

    Returns:
        DataFrame with standardized columns and formatting
    """
    df = pd.DataFrame(projects)

    # Ensure we have all expected columns
    for col in OUTPUT_PROJECT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Format pool fraction BEFORE reordering (while pool_fraction column still exists)
    if "pool_fraction" in df.columns:
        df["Pool Fraction (%)"] = df["pool_fraction"] * 100

    # Reorder columns
    df = df[OUTPUT_PROJECT_COLUMNS]

    return df
