# Pooling Calculator - Implementation TODO

## Phase 1: Project Setup & Infrastructure

### 1.1 Initialize Python Project Structure
- [ ] Create `pyproject.toml` with uv configuration
  - Set Python version requirement (3.11+)
  - Define project metadata (name, version, description)
  - Configure build system
- [ ] Create `.gitignore` for Python/uv projects
- [ ] Set up directory structure:
  - [ ] `src/pooling_calculator/` - main package
  - [ ] `tests/` - test suite
  - [ ] `docker/` - containerization
  - [ ] `data/` - example datasets

### 1.2 Core Dependencies
- [ ] Add dependencies to `pyproject.toml`:
  - [ ] pandas - spreadsheet processing
  - [ ] openpyxl - Excel file I/O
  - [ ] gradio - web UI framework
  - [ ] pydantic - data validation and models
- [ ] Add dev dependencies:
  - [ ] pytest - testing framework
  - [ ] pytest-cov - test coverage
  - [ ] black - code formatting (optional)
  - [ ] ruff - linting (optional)
- [ ] Run `uv sync` to create virtual environment

---

## Phase 2: Core Data Models

### 2.1 Configuration Module (`config.py`)
- [ ] Define scientific constants:
  - [ ] `MW_PER_BP = 660` (g/mol per base pair for dsDNA)
  - [ ] `DEFAULT_MIN_VOLUME_UL = 1.0` (minimum pipetting volume)
  - [ ] `DEFAULT_SHEET_NAME = None` (read first sheet)
- [ ] Define column name constants (required input columns)
- [ ] Define validation thresholds (warnings vs errors)
- [ ] Add app version string

### 2.2 Data Models (`models.py`)
- [ ] Create `LibraryRecord` dataclass/Pydantic model:
  - [ ] `project_id: str`
  - [ ] `library_name: str`
  - [ ] `final_ng_per_ul: float`
  - [ ] `total_volume_ul: float`
  - [ ] `barcode: str`
  - [ ] `adjusted_peak_size_bp: float`
  - [ ] `empirical_nm: float | None`
  - [ ] `target_reads_m: float`
- [ ] Create `LibraryWithComputedFields` (extends LibraryRecord):
  - [ ] `computed_nm: float`
  - [ ] `effective_nm: float`
  - [ ] `volume_in_pool_ul: float`
  - [ ] `pool_fraction: float`
  - [ ] `expected_reads: float | None`
  - [ ] `flags: list[str]`
- [ ] Create `ProjectSummary` dataclass:
  - [ ] `project_id: str`
  - [ ] `library_count: int`
  - [ ] `total_volume_ul: float`
  - [ ] `pool_fraction: float`
  - [ ] `expected_reads_m: float | None`
- [ ] Create `PoolingParams` for global parameters:
  - [ ] `desired_total_volume_ul: float`
  - [ ] `min_volume_ul: float`
  - [ ] `max_volume_ul: float | None`
  - [ ] `total_reads_m: float | None`

---

## Phase 3: Input/Output Module

### 3.1 Spreadsheet Loading (`io.py`)
- [ ] Implement `load_spreadsheet(path_or_bytes) -> pd.DataFrame`:
  - [ ] Accept file path or bytes object
  - [ ] Support .xlsx files (openpyxl engine)
  - [ ] Read first sheet by default
  - [ ] Handle file read errors gracefully
  - [ ] Return raw DataFrame
- [ ] Add column name normalization:
  - [ ] Case-insensitive matching
  - [ ] Strip whitespace
  - [ ] Map to standard internal names

### 3.2 Results Export (`io.py`)
- [ ] Implement `export_results_to_excel(libraries, projects, ...) -> bytes`:
  - [ ] Create Excel workbook with multiple sheets:
    - [ ] Sheet 1: `PoolingPlan_Libraries` (detailed per-library plan)
    - [ ] Sheet 2: `PoolingPlan_Projects` (project-level summary)
    - [ ] Sheet 3: `InputSummary` (metadata, timestamp, version)
  - [ ] Format columns appropriately (numbers, percentages)
  - [ ] Add timestamp to metadata sheet
  - [ ] Return bytes for download
- [ ] Generate timestamped filename: `pooling_plan_YYYYMMDD_HHMMSS.xlsx`

---

## Phase 4: Validation Module

### 4.1 Column Validation (`validation.py`)
- [ ] Implement `validate_columns(df) -> list[str]`:
  - [ ] Check all required columns are present
  - [ ] Return list of missing column names
  - [ ] Handle case-insensitive matching

### 4.2 Row-Level Validation (`validation.py`)
- [ ] Implement `validate_rows(df) -> tuple[list[str], list[str]]`:
  - [ ] For each required column, check:
    - [ ] Not null/empty (for string fields)
    - [ ] Parseable as correct type (float for numeric)
    - [ ] Value constraints (e.g., > 0 for concentrations)
  - [ ] Return (errors, warnings)
  - [ ] Include row numbers and field names in messages

### 4.3 Uniqueness Validation (`validation.py`)
- [ ] Implement `validate_uniqueness(df) -> list[str]`:
  - [ ] Check `Library Name` uniqueness
  - [ ] Check `Barcodes` uniqueness
  - [ ] Return list of duplicate values with row numbers

### 4.4 Main Validation Orchestrator (`validation.py`)
- [ ] Implement `run_all_validations(df) -> ValidationResult`:
  - [ ] Run column validation (blocking)
  - [ ] Run row validation
  - [ ] Run uniqueness validation (blocking)
  - [ ] Aggregate all errors and warnings
  - [ ] Return structured result with:
    - [ ] `is_valid: bool`
    - [ ] `errors: list[str]`
    - [ ] `warnings: list[str]`
    - [ ] `summary: dict` (e.g., number of libraries, projects)

---

## Phase 5: Computation Engine

### 5.1 Molarity Calculation (`compute.py`)
- [ ] Implement `compute_effective_molarity(df) -> pd.DataFrame`:
  - [ ] For each row:
    - [ ] If `Empirical Library nM` is provided and > 0, use it
    - [ ] Otherwise calculate: `C_nM = (ng_per_ul * 1e6) / (660 * bp)`
  - [ ] Add columns: `computed_nm`, `effective_nm`
  - [ ] Flag invalid (NaN or zero) molarities

### 5.2 Volume Calculation (`compute.py`)
- [ ] Implement `compute_pool_volumes(df, params) -> pd.DataFrame`:
  - [ ] Extract effective molarity `C_i` and weight `w_i` for each library
  - [ ] Calculate raw volume factors: `v_raw[i] = w_i / C_i`
  - [ ] Sum total raw volume: `V_raw_total = sum(v_raw)`
  - [ ] Calculate scaling factor: `s = desired_volume / V_raw_total`
  - [ ] Calculate final volumes: `V[i] = v_raw[i] * s`
  - [ ] Perform sanity checks:
    - [ ] `V[i] <= total_volume_ul` (sufficient sample)
    - [ ] `V[i] >= min_volume_ul` (pipettable)
    - [ ] `V[i] <= max_volume_ul` (if specified)
  - [ ] Add flags for violations
  - [ ] Calculate derived metrics:
    - [ ] Pool fraction: `f[i] = (V[i] * C[i]) / sum(V[j] * C[j])`
    - [ ] Expected reads (if total reads provided)
  - [ ] Return DataFrame with computed fields

### 5.3 Project Aggregation (`compute.py`)
- [ ] Implement `summarize_by_project(df) -> pd.DataFrame`:
  - [ ] Group by `Project ID`
  - [ ] Aggregate:
    - [ ] Count libraries
    - [ ] Sum volumes
    - [ ] Sum pool fractions
    - [ ] Sum expected reads
  - [ ] Return project summary DataFrame

---

## Phase 6: Gradio UI

### 6.1 UI Layout (`ui.py`)
- [ ] Define Gradio interface using `gr.Blocks`:
  - [ ] **Panel 1: File Upload**
    - [ ] File upload component (accept .xlsx)
    - [ ] Display upload status
  - [ ] **Panel 2: Global Parameters**
    - [ ] Number input: Desired total pool volume (µl)
    - [ ] Number input: Minimum per-library volume (µl, default=1.0)
    - [ ] Number input: Maximum per-library volume (µl, optional)
    - [ ] Number input: Total reads (M, optional)
  - [ ] **Panel 3: Validation Messages**
    - [ ] Text area for errors (red styling)
    - [ ] Text area for warnings (yellow styling)
    - [ ] Text area for summary (number of libraries, projects)
  - [ ] **Panel 4: Results**
    - [ ] Tab 1: Library-level table (Gradio DataFrame)
    - [ ] Tab 2: Project-level table (Gradio DataFrame)
  - [ ] **Panel 5: Export**
    - [ ] Button: "Download Pooling Plan (.xlsx)"
    - [ ] File download component

### 6.2 Event Handlers (`ui.py`)
- [ ] `on_file_upload(file) -> validation_messages`:
  - [ ] Load spreadsheet
  - [ ] Run validation
  - [ ] Display errors/warnings
  - [ ] Enable/disable "Calculate" button based on validation
  - [ ] Store validated DataFrame in state
- [ ] `on_calculate_click(df, params) -> (library_table, project_table)`:
  - [ ] Compute effective molarities
  - [ ] Compute pool volumes
  - [ ] Summarize by project
  - [ ] Display results in tables
  - [ ] Enable export button
  - [ ] Store results in state
- [ ] `on_export_click(libraries, projects) -> file`:
  - [ ] Generate Excel file
  - [ ] Return file for download

### 6.3 App Entry Point (`ui.py`)
- [ ] Create `build_app() -> gr.Blocks` function
- [ ] Add `if __name__ == "__main__":` block:
  - [ ] Call `build_app().launch()`
  - [ ] Configure server settings (port, share, etc.)

---

## Phase 7: Testing

### 7.1 Unit Tests - Computation
- [ ] `tests/test_compute.py`:
  - [ ] Test molarity calculation:
    - [ ] Known concentration + fragment size → expected nM
    - [ ] Empirical nM overrides calculated nM
    - [ ] Zero/NaN fragment size → flagged as invalid
  - [ ] Test volume calculation:
    - [ ] Two libraries, equal weights → equal volumes (equimolar)
    - [ ] Two libraries, different weights → proportional volumes
    - [ ] Insufficient sample volume → flagged
    - [ ] Below minimum pipetting volume → flagged
  - [ ] Test project aggregation:
    - [ ] Group by project ID
    - [ ] Sum volumes and fractions correctly

### 7.2 Unit Tests - Validation
- [ ] `tests/test_validation.py`:
  - [ ] Missing required column → error returned
  - [ ] Non-numeric value in numeric field → error
  - [ ] Negative concentration → error
  - [ ] Duplicate library name → error
  - [ ] Duplicate barcode → error
  - [ ] Valid input → no errors

### 7.3 Unit Tests - I/O
- [ ] `tests/test_io.py`:
  - [ ] Load valid .xlsx file → DataFrame returned
  - [ ] Export results → valid Excel file with multiple sheets
  - [ ] Column name normalization (case, whitespace)

### 7.4 Integration Tests
- [ ] `tests/test_integration.py`:
  - [ ] Create small test fixture (5-10 libraries, 2-3 projects)
  - [ ] Full pipeline: load → validate → compute → export
  - [ ] Verify output matches expected values

### 7.5 Test Fixtures
- [ ] `tests/fixtures/`:
  - [ ] Create `valid_pool.xlsx` (small valid dataset)
  - [ ] Create `invalid_pool_missing_column.xlsx`
  - [ ] Create `invalid_pool_duplicate_barcode.xlsx`
  - [ ] Store expected outputs for regression tests

---

## Phase 8: Docker & Deployment

### 8.1 Dockerfile
- [ ] `docker/Dockerfile`:
  - [ ] Base image: `python:3.11-slim`
  - [ ] Install system dependencies (if needed for openpyxl)
  - [ ] Copy project files
  - [ ] Install uv
  - [ ] Run `uv sync --frozen`
  - [ ] Expose port 7860 (Gradio default)
  - [ ] Set entrypoint: `uv run python -m pooling_calculator.ui`

### 8.2 Docker Compose (Optional)
- [ ] `docker/docker-compose.yml`:
  - [ ] Define service for pooling calculator
  - [ ] Map port 7860
  - [ ] Mount volumes if needed for data

### 8.3 Deployment Documentation
- [ ] Update README with:
  - [ ] Local setup instructions (`uv sync`, run command)
  - [ ] Docker build and run instructions
  - [ ] Usage guide (upload file, set parameters, download results)

---

## Phase 9: Documentation & Polish

### 9.1 Example Data
- [ ] Create `data/example_pool.xlsx`:
  - [ ] 20-30 realistic libraries
  - [ ] 3-4 different projects
  - [ ] Variety of concentrations and fragment sizes
  - [ ] Include 1-2 libraries with empirical nM

### 9.2 User Documentation
- [ ] Update README.md:
  - [ ] Project overview (what it does, why it's useful)
  - [ ] Installation instructions
  - [ ] Usage tutorial with screenshots
  - [ ] Input file format specification
  - [ ] Output file explanation
  - [ ] FAQ section
  - [ ] Troubleshooting common issues

### 9.3 Code Documentation
- [ ] Add docstrings to all public functions:
  - [ ] Parameter descriptions with types
  - [ ] Return value descriptions
  - [ ] Example usage
- [ ] Add module-level docstrings
- [ ] Add inline comments for complex calculations (formula references)

### 9.4 Packaging & Distribution
- [ ] Verify `pyproject.toml` completeness:
  - [ ] Project metadata
  - [ ] Entry points (if creating CLI)
  - [ ] License
  - [ ] Keywords
- [ ] Test installation from fresh environment
- [ ] Consider publishing to PyPI (optional)

---

## Phase 10: Future Enhancements (Post-MVP)

- [ ] Support CSV input files
- [ ] Custom sub-pool definitions (beyond Project ID)
- [ ] Per-project weighting (not just per-library)
- [ ] Export to liquid handler formats (Hamilton, Tecan, etc.)
- [ ] Dilution calculator (if library concentrations too high)
- [ ] Multi-step pooling workflow (hierarchical pooling)
- [ ] Batch processing (multiple pools at once)
- [ ] Save/load pooling parameters as presets
- [ ] API mode (REST endpoints) for integration with LIMS
- [ ] Advanced visualization (interactive plots of pool composition)

---

## Development Workflow Notes

### Testing Strategy
- Run unit tests after each module implementation
- Run integration tests before major commits
- Aim for >80% code coverage on core logic (compute, validation)

### Git Workflow
- Use conventional commits format
- Feature branches for each major phase
- Merge to main after tests pass

### Quality Checks
- Follow "Writing Functions Best Practices" from CLAUDE.md
- Keep functions simple and testable
- Avoid premature abstraction
- Prefer integration tests over heavy mocking

---

**Last Updated:** 2025-12-16
**Current Phase:** Phase 1 - Project Setup
