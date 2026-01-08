"""
Configuration constants and defaults for Pooling Calculator.

This module contains scientific constants, default parameters, and column name
mappings used throughout the application.
"""

from typing import Final

# ============================================================================
# Scientific Constants
# ============================================================================

# Average molecular weight per base pair for double-stranded DNA (g/mol)
MW_PER_BP: Final[float] = 660.0

# ============================================================================
# Default Parameters
# ============================================================================

# Minimum pipetting volume (µl) - below this is typically not accurate
DEFAULT_MIN_VOLUME_UL: Final[float] = 1.0

# Maximum pipetting volume (µl) - None means no limit
DEFAULT_MAX_VOLUME_UL: Final[float | None] = None

# Default total pool volume (µl)
DEFAULT_POOL_VOLUME_UL: Final[float] = 50.0

# Default Excel sheet to read (None = first sheet)
DEFAULT_SHEET_NAME: Final[str | None] = None

# ============================================================================
# Volume Calculation Parameters (Based on 7050I_miRNA_pool_copy.xlsx)
# ============================================================================

# Scaling factor for volume calculation (Cell AA4 in reference spreadsheet)
# Formula: stock_vol = scaling_factor / adj_lib_nM * target_reads_M
# Lower values = smaller volumes, Higher values = larger volumes
# Typical range: 0.05 - 0.5
DEFAULT_SCALING_FACTOR: Final[float] = 0.1

# Pre-dilution thresholds (Column Z logic in reference spreadsheet)
# These thresholds determine when samples need to be diluted before pipetting
# to ensure volumes are large enough for accurate pipetting

# IMPORTANT: These values are instrument-specific and may need adjustment
# based on your pipette accuracy specifications. Consult your lab's SOPs.

# If calculated stock volume < 0.2 µL: recommend 10x dilution
# This threshold is based on typical pipette accuracy limits
PRE_DILUTE_THRESHOLD_10X: Final[float] = 0.2

# If calculated stock volume < 0.795 µL: recommend 5x dilution
# Intermediate threshold for volumes that are pipettable but near the limit
PRE_DILUTE_THRESHOLD_5X: Final[float] = 0.795

# Absolute minimum pipettable volume (informational, for warnings)
# Volumes below this are generally not accurate even with best practices
ABSOLUTE_MIN_PIPETTABLE_VOLUME_UL: Final[float] = 0.08

# ============================================================================
# Input Column Names (Case-Insensitive Matching)
# ============================================================================

# Required columns in input spreadsheet
REQUIRED_COLUMNS: Final[list[str]] = [
    "Project ID",
    "Library Name",
    "Final ng/ul",
    "Total Volume",
    "Barcodes",
    "Adjusted peak size",
    "Target Reads (M)",
]

# Optional columns
OPTIONAL_COLUMNS: Final[list[str]] = [
    "Empirical Library nM",
]

# Column name aliases (for flexible matching)
# Maps alternative names to standard internal names
COLUMN_ALIASES: Final[dict[str, str]] = {
    # Project ID variants
    "project_id": "Project ID",
    "project": "Project ID",
    "projectid": "Project ID",
    # Library Name variants
    "library_name": "Library Name",
    "library": "Library Name",
    "sample_name": "Library Name",
    "sample": "Library Name",
    # Concentration variants
    "final_ng_ul": "Final ng/ul",
    "final ng/µl": "Final ng/ul",
    "concentration": "Final ng/ul",
    "conc": "Final ng/ul",
    # Volume variants
    "total_volume": "Total Volume",
    "volume": "Total Volume",
    "vol": "Total Volume",
    # Barcode variants
    "barcode": "Barcodes",
    "index": "Barcodes",
    "indices": "Barcodes",
    # Fragment size variants
    "adjusted_peak_size": "Adjusted peak size",
    "peak_size": "Adjusted peak size",
    "fragment_size": "Adjusted peak size",
    "size": "Adjusted peak size",
    # Empirical molarity variants
    "empirical_library_nm": "Empirical Library nM",
    "empirical_nm": "Empirical Library nM",
    "qpcr_nm": "Empirical Library nM",
    # Target reads variants
    "target_reads_m": "Target Reads (M)",
    "target_reads": "Target Reads (M)",
    "reads": "Target Reads (M)",
}

# ============================================================================
# Validation Thresholds
# ============================================================================

# Concentration thresholds (ng/µl)
MIN_CONCENTRATION_NG_UL: Final[float] = 0.01  # Below this: error
WARN_LOW_CONCENTRATION_NG_UL: Final[float] = 0.1  # Below this: warning
WARN_HIGH_CONCENTRATION_NG_UL: Final[float] = 1000.0  # Above this: warning

# Fragment size thresholds (bp)
MIN_FRAGMENT_SIZE_BP: Final[float] = 50  # Below this: error
WARN_LOW_FRAGMENT_SIZE_BP: Final[float] = 100  # Below this: warning
WARN_HIGH_FRAGMENT_SIZE_BP: Final[float] = 10000  # Above this: warning

# Volume thresholds (µl)
MIN_TOTAL_VOLUME_UL: Final[float] = 0.1  # Below this: error
WARN_LOW_TOTAL_VOLUME_UL: Final[float] = 5.0  # Below this: warning

# Molarity thresholds (nM)
MIN_MOLARITY_NM: Final[float] = 0.01  # Below this: error
WARN_LOW_MOLARITY_NM: Final[float] = 0.1  # Below this: warning
WARN_HIGH_MOLARITY_NM: Final[float] = 1000.0  # Above this: warning

# Target reads thresholds (M)
MIN_TARGET_READS_M: Final[float] = 0.1  # Below this: error

# ============================================================================
# Output Column Names
# ============================================================================

OUTPUT_LIBRARY_COLUMNS: Final[list[str]] = [
    "Project ID",
    "Library Name",
    "Barcodes",
    "Final ng/ul",
    "Adjusted peak size",
    "Empirical Library nM",
    "Calculated nM",
    "Effective nM (Use)",
    "Adjusted lib nM",
    "Target Reads (M)",
    "Stock Volume (µl)",
    "Pre-Dilute Factor",
    "Final Volume (µl)",
    "Pool Fraction",
    "Expected Reads (M)",
    "Flags",
]

OUTPUT_PROJECT_COLUMNS: Final[list[str]] = [
    "Project ID",
    "Library Count",
    "Total Volume (µl)",
    "Pool Fraction (%)",
    "Expected Reads (M)",
]

# ============================================================================
# Validation Messages
# ============================================================================

ERROR_MISSING_COLUMN: Final[str] = "Missing required column: {column}"
ERROR_NEGATIVE_VALUE: Final[str] = "Row {row}, {column}: Value must be > 0, got {value}"
ERROR_INVALID_TYPE: Final[str] = "Row {row}, {column}: Cannot parse as {dtype}, got '{value}'"
ERROR_DUPLICATE_VALUE: Final[str] = "Duplicate {column} found: '{value}' in rows {rows}"
ERROR_EMPTY_VALUE: Final[str] = "Row {row}, {column}: Value cannot be empty"

WARN_LOW_CONCENTRATION: Final[str] = (
    "Row {row}, Final ng/ul: Very low concentration ({value:.3f} ng/µl) - library may be too dilute"
)
WARN_HIGH_CONCENTRATION: Final[str] = (
    "Row {row}, Final ng/ul: Very high concentration ({value:.1f} ng/µl) - consider diluting"
)
WARN_LOW_VOLUME: Final[str] = (
    "Row {row}, Total Volume: Low volume ({value:.1f} µl) - may be insufficient for pooling"
)
WARN_INSUFFICIENT_VOLUME: Final[str] = "Insufficient sample volume (need {needed:.2f} µl, have {available:.2f} µl)"
WARN_BELOW_MIN_PIPETTE: Final[str] = "Below minimum pipetting volume ({volume:.2f} µl < {min_vol:.2f} µl)"
WARN_ABOVE_MAX_PIPETTE: Final[str] = "Above maximum pipetting volume ({volume:.2f} µl > {max_vol:.2f} µl)"

# ============================================================================
# Application Metadata
# ============================================================================

APP_VERSION: Final[str] = "0.1.0"
APP_NAME: Final[str] = "Pooling Calculator"
APP_DESCRIPTION: Final[str] = "NGS Library Pooling Utility"

# ============================================================================
# Helper Functions
# ============================================================================


def normalize_column_name(name: str) -> str:
    """
    Normalize a column name for matching.

    Converts to lowercase, strips whitespace, and looks up aliases.

    Args:
        name: Raw column name from input file

    Returns:
        Standardized column name, or original if no match found
    """
    # Strip whitespace and convert to lowercase
    normalized = name.strip().lower()

    # Check if it's an alias
    if normalized in COLUMN_ALIASES:
        return COLUMN_ALIASES[normalized]

    # Check if it matches a required/optional column (case-insensitive)
    for col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if col.lower() == normalized:
            return col

    # Return original if no match
    return name


def get_all_valid_column_names() -> list[str]:
    """
    Get list of all valid column names (required + optional).

    Returns:
        List of standard column names
    """
    return REQUIRED_COLUMNS + OPTIONAL_COLUMNS


# ============================================================================
# Hierarchical Pooling Configuration
# ============================================================================

# Strategy Selection
MAX_LIBRARIES_PER_POOL = 96
"""Maximum libraries in a single pooling operation (typical 96-well plate)."""

MIN_SUBPOOLS_FOR_HIERARCHICAL = 5
"""Minimum number of sub-pools to justify hierarchical approach."""

HIERARCHICAL_GROUPING_COLUMNS = ["Project ID"]
"""Default columns to consider for hierarchical pooling grouping."""

# Sub-pool Configuration
DEFAULT_MAX_LIBRARIES_PER_SUBPOOL = 96
"""Default maximum libraries per sub-pool (96-well plate limit)."""

# Workflow Thresholds
LARGE_EXPERIMENT_THRESHOLD = 100
"""Number of libraries above which hierarchical pooling is strongly recommended."""

SUBPOOL_BALANCE_TOLERANCE = 0.1
"""Maximum acceptable imbalance in sub-pool concentrations (10% variation)."""
