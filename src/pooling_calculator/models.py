"""
Data models for Pooling Calculator using Pydantic.

This module defines the core data structures used throughout the application,
with runtime validation and type safety provided by Pydantic.
"""

from datetime import datetime
from enum import Enum
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


# ============================================================================
# Hierarchical Pooling Models
# ============================================================================


class PoolingStage(str, Enum):
    """
    Enumeration of pooling stages in hierarchical workflow.

    Stages are ordered from earliest to latest in the workflow.
    """

    LIBRARY_TO_SUBPOOL = "library_to_subpool"
    SUBPOOL_TO_MASTER = "subpool_to_master"
    # Future: MASTER_TO_SUPERPOOL = "master_to_superpool"


class SubPoolRecord(BaseModel):
    """
    Represents an intermediate pool created from multiple libraries.

    Sub-pools are the result of pooling libraries together in the first stage
    of hierarchical pooling. They are then pooled together to create the master pool.
    """

    subpool_id: str = Field(..., min_length=1, description="Unique identifier for this sub-pool")
    member_libraries: list[str] = Field(..., min_length=1, description="Library names in this sub-pool")
    calculated_nm: float = Field(..., gt=0, description="Effective molarity after pooling (nM)")
    total_volume_ul: float = Field(..., gt=0, description="Total volume of this sub-pool (µl)")
    target_reads_m: float = Field(..., gt=0, description="Sum of target reads from member libraries (M)")
    creation_date: datetime = Field(default_factory=datetime.now, description="When this sub-pool was created")

    # Optional metadata
    parent_project_id: str | None = Field(None, description="Project ID if grouped by project")
    custom_grouping: dict[str, Any] | None = Field(None, description="Custom grouping metadata")

    @field_validator("subpool_id")
    @classmethod
    def strip_whitespace_subpool_id(cls, v: str) -> str:
        """Strip leading/trailing whitespace from subpool_id."""
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "subpool_id": "ProjectA_pool",
                    "member_libraries": ["Lib001", "Lib002", "Lib003"],
                    "calculated_nm": 15.5,
                    "total_volume_ul": 50.0,
                    "target_reads_m": 300.0,
                    "creation_date": "2025-01-07T12:00:00",
                    "parent_project_id": "ProjectA",
                    "custom_grouping": None,
                }
            ]
        }
    }


class PoolingStageData(BaseModel):
    """
    Data for a single stage in the hierarchical pooling workflow.

    Each stage represents one pooling operation (e.g., libraries → sub-pools,
    or sub-pools → master pool).
    """

    stage: PoolingStage = Field(..., description="Which stage this represents")
    stage_number: int = Field(..., ge=1, description="Sequential stage number (1, 2, 3, ...)")
    input_count: int = Field(..., gt=0, description="Number of inputs being pooled")
    output_count: int = Field(..., gt=0, description="Number of outputs created")

    # Calculated results for this stage
    volumes_df_json: list[dict[str, Any]] = Field(..., description="DataFrame with volumes as JSON (records format)")
    total_pipetting_steps: int = Field(..., ge=0, description="Total number of pipetting operations")

    # Stage-specific metadata
    description: str = Field(..., description="Human-readable description of this stage")
    warnings: list[str] = Field(default_factory=list, description="Warnings generated during this stage")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "stage": "library_to_subpool",
                    "stage_number": 1,
                    "input_count": 400,
                    "output_count": 8,
                    "volumes_df_json": {},
                    "total_pipetting_steps": 400,
                    "description": "Pool 400 libraries into 8 project-based sub-pools",
                    "warnings": [],
                }
            ]
        }
    }


class HierarchicalPoolingPlan(BaseModel):
    """
    Complete multi-step pooling workflow plan.

    This model represents the entire hierarchical pooling strategy,
    including all stages from libraries to final master pool.
    """

    stages: list[PoolingStageData] = Field(..., min_length=1, description="Ordered list of pooling stages")
    final_pool_volume_ul: float = Field(..., gt=0, description="Final master pool volume (µl)")
    total_libraries: int = Field(..., gt=0, description="Total number of input libraries")
    total_subpools: int = Field(..., ge=0, description="Total number of intermediate sub-pools")

    # Strategy metadata
    strategy: str = Field(..., description="Pooling strategy used (e.g., 'hierarchical', 'single-stage')")
    grouping_method: str = Field(..., description="How sub-pools were defined (e.g., 'by_project', 'manual')")

    # Timestamps and parameters
    created_at: datetime = Field(default_factory=datetime.now, description="When this plan was created")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Global pooling parameters")

    # Summary statistics
    total_pipetting_steps: int = Field(..., ge=0, description="Total pipetting steps across all stages")
    estimated_time_minutes: float | None = Field(None, ge=0, description="Estimated lab time (optional)")

    @field_validator("stages")
    @classmethod
    def stages_must_be_sequential(cls, v: list[PoolingStageData]) -> list[PoolingStageData]:
        """Validate that stage numbers are sequential starting from 1."""
        if not v:
            return v

        expected_stage_num = 1
        for stage in v:
            if stage.stage_number != expected_stage_num:
                raise ValueError(
                    f"Stage numbers must be sequential. Expected {expected_stage_num}, "
                    f"got {stage.stage_number}"
                )
            expected_stage_num += 1

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "stages": [],
                    "final_pool_volume_ul": 20.0,
                    "total_libraries": 400,
                    "total_subpools": 8,
                    "strategy": "hierarchical",
                    "grouping_method": "by_project",
                    "created_at": "2025-01-07T12:00:00",
                    "parameters": {"scaling_factor": 0.1},
                    "total_pipetting_steps": 408,
                    "estimated_time_minutes": 120.0,
                }
            ]
        }
    }


# ============================================================================
# Pre-Pooling Models
# ============================================================================


class PrePoolDefinition(BaseModel):
    """
    User-defined pre-pool grouping specification.

    Pre-pools allow users to manually group specific libraries together
    before the final pooling step. This is useful for workflow optimization
    and grouping similar samples.
    """

    prepool_id: str = Field(..., min_length=1, description="Unique identifier (e.g., 'Prepool_1')")
    prepool_name: str = Field(..., min_length=1, description="User-friendly display name")
    member_library_names: list[str] = Field(..., min_length=1, description="List of library names to include")
    created_at: datetime = Field(default_factory=datetime.now, description="When this pre-pool was defined")
    notes: str | None = Field(None, description="Optional notes about this pre-pool")

    @field_validator("prepool_id", "prepool_name")
    @classmethod
    def strip_whitespace_prepool(cls, v: str) -> str:
        """Strip leading/trailing whitespace."""
        return v.strip()

    @field_validator("member_library_names")
    @classmethod
    def validate_unique_libraries(cls, v: list[str]) -> list[str]:
        """Ensure no duplicate library names within a pre-pool."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate library names found in member_library_names")
        return [lib.strip() for lib in v]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prepool_id": "prepool_1",
                    "prepool_name": "Prepool 1",
                    "member_library_names": ["Lib001", "Lib002", "Lib003"],
                    "created_at": "2025-01-09T10:00:00",
                    "notes": "High concentration samples",
                }
            ]
        }
    }


class PrePoolCalculationResult(BaseModel):
    """
    Result of calculating pooling volumes for a user-defined pre-pool.

    Contains both the original definition and the calculated properties
    of the pre-pool after its member libraries are pooled together.
    """

    prepool_definition: PrePoolDefinition = Field(..., description="Original pre-pool specification")
    calculated_nm: float = Field(..., gt=0, description="Effective molarity after pooling members (nM)")
    total_volume_ul: float = Field(..., gt=0, description="Total volume of this pre-pool (µl)")
    target_reads_m: float = Field(..., gt=0, description="Sum of target reads from all members (M)")
    member_volumes_json: list[dict[str, Any]] = Field(..., description="Per-library volumes within prepool (JSON)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prepool_definition": {
                        "prepool_id": "prepool_1",
                        "prepool_name": "Prepool 1",
                        "member_library_names": ["Lib001", "Lib002"],
                        "created_at": "2025-01-09T10:00:00",
                        "notes": None,
                    },
                    "calculated_nm": 25.3,
                    "total_volume_ul": 30.0,
                    "target_reads_m": 20.0,
                    "member_volumes_json": [],
                }
            ]
        }
    }


class PrePoolingPlan(BaseModel):
    """
    Complete pre-pooling workflow result.

    Represents the entire calculation when user-defined pre-pools are used,
    including both pre-pool details and the final pool composition.
    """

    prepools: list[PrePoolCalculationResult] = Field(default_factory=list, description="All calculated pre-pools")
    remaining_libraries_json: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Libraries NOT in any pre-pool (JSON)"
    )
    final_pool_json: list[dict[str, Any]] = Field(..., description="Final pool with individuals + prepools (JSON)")

    # Summary statistics
    total_libraries: int = Field(..., ge=0, description="Total number of input libraries")
    libraries_in_prepools: int = Field(..., ge=0, description="Number of libraries assigned to pre-pools")
    standalone_libraries: int = Field(..., ge=0, description="Number of libraries NOT in any pre-pool")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="When this plan was created")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Calculation parameters used")

    @field_validator("libraries_in_prepools", "standalone_libraries")
    @classmethod
    def validate_library_counts(cls, v: int, info) -> int:
        """Validate that library counts sum correctly."""
        data = info.data
        if "total_libraries" in data:
            total = data["total_libraries"]
            in_prepools = data.get("libraries_in_prepools", 0)
            standalone = data.get("standalone_libraries", 0)

            if in_prepools + standalone != total:
                raise ValueError(
                    f"Library counts don't sum: {in_prepools} + {standalone} != {total}"
                )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prepools": [],
                    "remaining_libraries_json": [],
                    "final_pool_json": [],
                    "total_libraries": 48,
                    "libraries_in_prepools": 11,
                    "standalone_libraries": 37,
                    "created_at": "2025-01-09T10:00:00",
                    "parameters": {"scaling_factor": 0.1},
                }
            ]
        }
    }
