"""
Data models for Pooling Calculator using Pydantic.

This module defines the core data structures used throughout the application,
with runtime validation and type safety provided by Pydantic.
"""

from typing import Any
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Input Data Models
# ============================================================================


class LibraryRecord(BaseModel):
    """
    Represents a single library's input data from the spreadsheet.

    This is the raw input before any calculations are performed.
    """

    project_id: str = Field(..., min_length=1, description="Project identifier for grouping")
    library_name: str = Field(..., min_length=1, description="Unique library identifier")
    final_ng_per_ul: float = Field(..., gt=0, description="Concentration in ng/µl")
    total_volume_ul: float = Field(..., gt=0, description="Available volume in µl")
    barcode: str = Field(..., min_length=1, description="Unique barcode/index sequence")
    adjusted_peak_size_bp: float = Field(..., gt=0, description="Average fragment length in base pairs")
    empirical_nm: float | None = Field(None, gt=0, description="Optional qPCR-measured molarity in nM")
    target_reads_m: float = Field(..., gt=0, description="Target read allocation in millions")

    @field_validator("project_id", "library_name", "barcode")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from string fields."""
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_id": "Project_A",
                    "library_name": "Lib_001",
                    "final_ng_per_ul": 12.5,
                    "total_volume_ul": 30.0,
                    "barcode": "ATCG-GGTA",
                    "adjusted_peak_size_bp": 450.0,
                    "empirical_nm": None,
                    "target_reads_m": 10.0,
                }
            ]
        }
    }


class LibraryWithComputedFields(LibraryRecord):
    """
    Extends LibraryRecord with calculated fields from pooling algorithms.

    This model represents a library after molarity and volume calculations.
    """

    computed_nm: float = Field(..., description="Calculated molarity from concentration and size")
    effective_nm: float = Field(..., description="Final molarity (empirical or computed)")
    volume_in_pool_ul: float = Field(..., ge=0, description="Volume to pipette into pool")
    pool_fraction: float = Field(..., ge=0, le=1, description="Fraction of total pool (0-1)")
    expected_reads: float | None = Field(None, ge=0, description="Expected reads if total provided")
    flags: list[str] = Field(default_factory=list, description="Validation warnings/errors")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_id": "Project_A",
                    "library_name": "Lib_001",
                    "final_ng_per_ul": 12.5,
                    "total_volume_ul": 30.0,
                    "barcode": "ATCG-GGTA",
                    "adjusted_peak_size_bp": 450.0,
                    "empirical_nm": None,
                    "target_reads_m": 10.0,
                    "computed_nm": 42.09,
                    "effective_nm": 42.09,
                    "volume_in_pool_ul": 5.25,
                    "pool_fraction": 0.33,
                    "expected_reads": 33.5,
                    "flags": [],
                }
            ]
        }
    }


# ============================================================================
# Aggregation Models
# ============================================================================


class ProjectSummary(BaseModel):
    """
    Aggregated metrics for a project (group of libraries).

    Summarizes pool contribution at the project level.
    """

    project_id: str = Field(..., min_length=1, description="Project identifier")
    library_count: int = Field(..., ge=1, description="Number of libraries in this project")
    total_volume_ul: float = Field(..., ge=0, description="Sum of volumes from all libraries")
    pool_fraction: float = Field(..., ge=0, le=1, description="Fraction of total pool (0-1)")
    expected_reads_m: float | None = Field(None, ge=0, description="Expected total reads (millions)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_id": "Project_A",
                    "library_count": 10,
                    "total_volume_ul": 52.5,
                    "pool_fraction": 0.33,
                    "expected_reads_m": 100.5,
                }
            ]
        }
    }


# ============================================================================
# Parameter Models
# ============================================================================


class PoolingParams(BaseModel):
    """
    Global parameters for pooling calculations.

    These are user-specified settings that control the pooling algorithm.
    """

    desired_total_volume_ul: float = Field(..., gt=0, description="Target pool volume in µl")
    min_volume_ul: float = Field(1.0, gt=0, description="Minimum pipettable volume in µl")
    max_volume_ul: float | None = Field(None, gt=0, description="Maximum pipettable volume (optional)")
    total_reads_m: float | None = Field(None, gt=0, description="Total sequencing reads (millions, optional)")

    @field_validator("max_volume_ul")
    @classmethod
    def validate_max_volume(cls, v: float | None, info) -> float | None:
        """Ensure max_volume > min_volume if both are set."""
        if v is not None:
            min_vol = info.data.get("min_volume_ul", 1.0)
            if v <= min_vol:
                raise ValueError(f"max_volume_ul ({v}) must be > min_volume_ul ({min_vol})")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "desired_total_volume_ul": 50.0,
                    "min_volume_ul": 1.0,
                    "max_volume_ul": None,
                    "total_reads_m": 100.0,
                }
            ]
        }
    }


# ============================================================================
# Validation Models
# ============================================================================


class ValidationResult(BaseModel):
    """
    Result of input validation checks.

    Contains all errors, warnings, and summary information.
    """

    is_valid: bool = Field(..., description="True if no blocking errors")
    errors: list[str] = Field(default_factory=list, description="Blocking validation errors")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics")

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def get_report(self) -> str:
        """
        Generate a human-readable report.

        Returns:
            Formatted string with errors, warnings, and summary
        """
        lines = []

        if self.has_errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            lines.append("")

        if self.has_warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        if self.summary:
            lines.append("SUMMARY:")
            for key, value in self.summary.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "is_valid": True,
                    "errors": [],
                    "warnings": [
                        "Row 5, Final ng/ul: Very low concentration (0.05 ng/µl)"
                    ],
                    "summary": {
                        "num_libraries": 24,
                        "num_projects": 3,
                        "projects": ["Project_A", "Project_B", "Project_C"],
                    },
                }
            ]
        }
    }


# ============================================================================
# Helper Functions for Model Creation
# ============================================================================


def create_library_from_dict(data: dict[str, Any]) -> LibraryRecord:
    """
    Create a LibraryRecord from a dictionary (e.g., from DataFrame row).

    Args:
        data: Dictionary with library data

    Returns:
        Validated LibraryRecord instance

    Raises:
        ValidationError: If data doesn't meet validation requirements
    """
    return LibraryRecord(**data)


def create_pooling_params(
    pool_volume: float,
    min_volume: float = 1.0,
    max_volume: float | None = None,
    total_reads: float | None = None,
) -> PoolingParams:
    """
    Create PoolingParams with defaults.

    Args:
        pool_volume: Desired total pool volume (µl)
        min_volume: Minimum pipetting volume (µl)
        max_volume: Maximum pipetting volume (µl), None for no limit
        total_reads: Total sequencing reads (millions), None if unknown

    Returns:
        Validated PoolingParams instance
    """
    return PoolingParams(
        desired_total_volume_ul=pool_volume,
        min_volume_ul=min_volume,
        max_volume_ul=max_volume,
        total_reads_m=total_reads,
    )
