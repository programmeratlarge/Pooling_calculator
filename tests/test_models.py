"""
Unit tests for Pydantic data models.

Tests validation, constraints, and helper functions for all models.
"""

import pytest
from pydantic import ValidationError

from pooling_calculator.models import (
    LibraryRecord,
    LibraryWithComputedFields,
    ProjectSummary,
    PoolingParams,
    ValidationResult,
    create_library_from_dict,
    create_pooling_params,
)


# ============================================================================
# LibraryRecord Tests
# ============================================================================


def test_library_record_valid():
    """Valid LibraryRecord should be created successfully."""
    lib = LibraryRecord(
        project_id="Project_A",
        library_name="Lib_001",
        final_ng_per_ul=12.5,
        total_volume_ul=30.0,
        barcode="ATCG-GGTA",
        adjusted_peak_size_bp=450.0,
        empirical_nm=None,
        target_reads_m=10.0,
    )
    assert lib.project_id == "Project_A"
    assert lib.library_name == "Lib_001"
    assert lib.final_ng_per_ul == 12.5
    assert lib.empirical_nm is None


def test_library_record_with_empirical_nm():
    """LibraryRecord with empirical nM should validate correctly."""
    lib = LibraryRecord(
        project_id="Project_B",
        library_name="Lib_002",
        final_ng_per_ul=10.0,
        total_volume_ul=25.0,
        barcode="GCTA-ATCG",
        adjusted_peak_size_bp=380.0,
        empirical_nm=35.2,
        target_reads_m=15.0,
    )
    assert lib.empirical_nm == 35.2


def test_library_record_strips_whitespace():
    """String fields should have whitespace stripped."""
    lib = LibraryRecord(
        project_id="  Project_A  ",
        library_name=" Lib_001 ",
        final_ng_per_ul=12.5,
        total_volume_ul=30.0,
        barcode=" ATCG-GGTA ",
        adjusted_peak_size_bp=450.0,
        target_reads_m=10.0,
    )
    assert lib.project_id == "Project_A"
    assert lib.library_name == "Lib_001"
    assert lib.barcode == "ATCG-GGTA"


def test_library_record_negative_concentration_fails():
    """Negative concentration should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        LibraryRecord(
            project_id="Project_A",
            library_name="Lib_001",
            final_ng_per_ul=-1.0,  # Invalid
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            target_reads_m=10.0,
        )
    assert "final_ng_per_ul" in str(exc_info.value)


def test_library_record_zero_concentration_fails():
    """Zero concentration should raise ValidationError."""
    with pytest.raises(ValidationError):
        LibraryRecord(
            project_id="Project_A",
            library_name="Lib_001",
            final_ng_per_ul=0.0,  # Invalid
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            target_reads_m=10.0,
        )


def test_library_record_empty_project_id_fails():
    """Empty project_id should raise ValidationError."""
    with pytest.raises(ValidationError):
        LibraryRecord(
            project_id="",  # Invalid
            library_name="Lib_001",
            final_ng_per_ul=12.5,
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            target_reads_m=10.0,
        )


def test_library_record_negative_empirical_nm_fails():
    """Negative empirical_nm should raise ValidationError."""
    with pytest.raises(ValidationError):
        LibraryRecord(
            project_id="Project_A",
            library_name="Lib_001",
            final_ng_per_ul=12.5,
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            empirical_nm=-5.0,  # Invalid
            target_reads_m=10.0,
        )


# ============================================================================
# LibraryWithComputedFields Tests
# ============================================================================


def test_library_with_computed_fields_valid():
    """Valid LibraryWithComputedFields should be created successfully."""
    lib = LibraryWithComputedFields(
        project_id="Project_A",
        library_name="Lib_001",
        final_ng_per_ul=12.5,
        total_volume_ul=30.0,
        barcode="ATCG-GGTA",
        adjusted_peak_size_bp=450.0,
        target_reads_m=10.0,
        computed_nm=42.09,
        effective_nm=42.09,
        volume_in_pool_ul=5.25,
        pool_fraction=0.33,
        expected_reads=33.5,
        flags=[],
    )
    assert lib.computed_nm == 42.09
    assert lib.effective_nm == 42.09
    assert lib.volume_in_pool_ul == 5.25
    assert lib.pool_fraction == 0.33
    assert lib.expected_reads == 33.5
    assert len(lib.flags) == 0


def test_library_with_flags():
    """LibraryWithComputedFields can have warning flags."""
    lib = LibraryWithComputedFields(
        project_id="Project_A",
        library_name="Lib_001",
        final_ng_per_ul=12.5,
        total_volume_ul=30.0,
        barcode="ATCG-GGTA",
        adjusted_peak_size_bp=450.0,
        target_reads_m=10.0,
        computed_nm=42.09,
        effective_nm=42.09,
        volume_in_pool_ul=0.5,  # Below minimum
        pool_fraction=0.33,
        flags=["Below minimum pipetting volume"],
    )
    assert len(lib.flags) == 1
    assert "Below minimum" in lib.flags[0]


def test_library_pool_fraction_above_one_fails():
    """Pool fraction > 1.0 should raise ValidationError."""
    with pytest.raises(ValidationError):
        LibraryWithComputedFields(
            project_id="Project_A",
            library_name="Lib_001",
            final_ng_per_ul=12.5,
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            target_reads_m=10.0,
            computed_nm=42.09,
            effective_nm=42.09,
            volume_in_pool_ul=5.25,
            pool_fraction=1.5,  # Invalid
        )


def test_library_negative_volume_fails():
    """Negative volume should raise ValidationError."""
    with pytest.raises(ValidationError):
        LibraryWithComputedFields(
            project_id="Project_A",
            library_name="Lib_001",
            final_ng_per_ul=12.5,
            total_volume_ul=30.0,
            barcode="ATCG-GGTA",
            adjusted_peak_size_bp=450.0,
            target_reads_m=10.0,
            computed_nm=42.09,
            effective_nm=42.09,
            volume_in_pool_ul=-1.0,  # Invalid
            pool_fraction=0.33,
        )


# ============================================================================
# ProjectSummary Tests
# ============================================================================


def test_project_summary_valid():
    """Valid ProjectSummary should be created successfully."""
    proj = ProjectSummary(
        project_id="Project_A",
        library_count=10,
        total_volume_ul=52.5,
        pool_fraction=0.33,
        expected_reads_m=100.5,
    )
    assert proj.project_id == "Project_A"
    assert proj.library_count == 10
    assert proj.total_volume_ul == 52.5
    assert proj.pool_fraction == 0.33
    assert proj.expected_reads_m == 100.5


def test_project_summary_without_expected_reads():
    """ProjectSummary without expected_reads should be valid."""
    proj = ProjectSummary(
        project_id="Project_B",
        library_count=5,
        total_volume_ul=25.0,
        pool_fraction=0.2,
        expected_reads_m=None,
    )
    assert proj.expected_reads_m is None


def test_project_summary_zero_libraries_fails():
    """Zero library_count should raise ValidationError."""
    with pytest.raises(ValidationError):
        ProjectSummary(
            project_id="Project_A",
            library_count=0,  # Invalid
            total_volume_ul=52.5,
            pool_fraction=0.33,
        )


# ============================================================================
# PoolingParams Tests
# ============================================================================


def test_pooling_params_valid():
    """Valid PoolingParams should be created successfully."""
    params = PoolingParams(
        desired_total_volume_ul=50.0,
        min_volume_ul=1.0,
        max_volume_ul=None,
        total_reads_m=100.0,
    )
    assert params.desired_total_volume_ul == 50.0
    assert params.min_volume_ul == 1.0
    assert params.max_volume_ul is None
    assert params.total_reads_m == 100.0


def test_pooling_params_with_max_volume():
    """PoolingParams with max_volume should validate correctly."""
    params = PoolingParams(
        desired_total_volume_ul=50.0,
        min_volume_ul=1.0,
        max_volume_ul=10.0,
    )
    assert params.max_volume_ul == 10.0


def test_pooling_params_max_less_than_min_fails():
    """max_volume < min_volume should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PoolingParams(
            desired_total_volume_ul=50.0,
            min_volume_ul=5.0,
            max_volume_ul=3.0,  # Invalid: less than min
        )
    assert "max_volume_ul" in str(exc_info.value)


def test_pooling_params_zero_pool_volume_fails():
    """Zero desired_total_volume_ul should raise ValidationError."""
    with pytest.raises(ValidationError):
        PoolingParams(
            desired_total_volume_ul=0.0,  # Invalid
            min_volume_ul=1.0,
        )


# ============================================================================
# ValidationResult Tests
# ============================================================================


def test_validation_result_valid():
    """Valid ValidationResult should be created successfully."""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])
    assert result.is_valid is True
    assert not result.has_errors
    assert not result.has_warnings


def test_validation_result_with_errors():
    """ValidationResult with errors should be created successfully."""
    result = ValidationResult(
        is_valid=False,
        errors=["Missing column: Project ID"],
        warnings=[],
    )
    assert result.is_valid is False
    assert result.has_errors
    assert len(result.errors) == 1


def test_validation_result_add_error():
    """add_error should add error and set is_valid to False."""
    result = ValidationResult(is_valid=True)
    result.add_error("Test error")
    assert result.is_valid is False
    assert result.has_errors
    assert "Test error" in result.errors


def test_validation_result_add_warning():
    """add_warning should add warning without changing is_valid."""
    result = ValidationResult(is_valid=True)
    result.add_warning("Test warning")
    assert result.is_valid is True
    assert result.has_warnings
    assert "Test warning" in result.warnings


def test_validation_result_get_report():
    """get_report should format errors, warnings, and summary."""
    result = ValidationResult(
        is_valid=False,
        errors=["Error 1", "Error 2"],
        warnings=["Warning 1"],
        summary={"num_libraries": 24, "num_projects": 3},
    )
    report = result.get_report()

    assert "ERRORS:" in report
    assert "Error 1" in report
    assert "Error 2" in report
    assert "WARNINGS:" in report
    assert "Warning 1" in report
    assert "SUMMARY:" in report
    assert "num_libraries: 24" in report


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_create_library_from_dict():
    """create_library_from_dict should create LibraryRecord from dict."""
    data = {
        "project_id": "Project_A",
        "library_name": "Lib_001",
        "final_ng_per_ul": 12.5,
        "total_volume_ul": 30.0,
        "barcode": "ATCG-GGTA",
        "adjusted_peak_size_bp": 450.0,
        "target_reads_m": 10.0,
    }
    lib = create_library_from_dict(data)
    assert isinstance(lib, LibraryRecord)
    assert lib.project_id == "Project_A"
    assert lib.library_name == "Lib_001"


def test_create_pooling_params_with_defaults():
    """create_pooling_params should use defaults for optional parameters."""
    params = create_pooling_params(pool_volume=50.0)
    assert params.desired_total_volume_ul == 50.0
    assert params.min_volume_ul == 1.0
    assert params.max_volume_ul is None
    assert params.total_reads_m is None


def test_create_pooling_params_all_args():
    """create_pooling_params should accept all parameters."""
    params = create_pooling_params(
        pool_volume=100.0, min_volume=2.0, max_volume=15.0, total_reads=200.0
    )
    assert params.desired_total_volume_ul == 100.0
    assert params.min_volume_ul == 2.0
    assert params.max_volume_ul == 15.0
    assert params.total_reads_m == 200.0
