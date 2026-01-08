# Pooling Calculator - Detailed Technical Specification

## Document Overview

**Version:** 1.0
**Last Updated:** 2025-12-16
**Status:** Initial Planning

This document provides the complete technical specification for the Pooling Calculator application, a tool for Next-Generation Sequencing (NGS) library pooling.

---

## 1. Executive Summary

### 1.1 Purpose

The Pooling Calculator automates the complex calculations required to pool DNA libraries for NGS sequencing. It ensures that each library contributes the correct number of molecules to achieve balanced read depth across samples, which is critical for accurate sequencing results.

### 1.2 Key Capabilities

1. **Molarity Conversion**: Convert mass concentrations (ng/µl) to molar concentrations (nM) using fragment length data
2. **Weighted Pooling**: Support both equimolar pooling and custom read allocation per library
3. **Volume Calculation**: Compute precise pipetting volumes for each library
4. **Sub-pool Management**: Aggregate libraries by project and ensure balanced representation
5. **Validation**: Comprehensive input validation with clear, actionable error messages
6. **Export**: Generate downloadable Excel protocols for lab execution

### 1.3 Target Users

- Molecular biologists preparing NGS libraries
- Core facility staff managing high-throughput sequencing
- Bioinformaticians designing sequencing experiments

---

## 2. Technical Architecture

### 2.1 Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Language | Python | 3.11+ | Modern type hints, performance, ecosystem |
| Package Manager | uv | Latest | Fast, reliable dependency management |
| UI Framework | Gradio | Latest | Rapid prototyping, built-in components |
| Data Processing | Pandas | Latest | Efficient tabular data operations |
| Excel I/O | openpyxl | Latest | .xlsx read/write support |
| Data Models | Pydantic | 2.x | Runtime validation, type safety |
| Testing | pytest | Latest | Comprehensive testing framework |
| Containerization | Docker | Latest | Reproducible deployment |

### 2.2 Project Structure

```
pooling_calculator/
├── pyproject.toml              # uv project definition
├── README.md                   # User-facing documentation
├── CLAUDE.md                   # AI assistant guidance
├── TODO.md                     # Implementation checklist
├── SPEC.md                     # This document
├── .gitignore
├── src/
│   └── pooling_calculator/
│       ├── __init__.py         # Package initialization
│       ├── config.py           # Constants and configuration
│       ├── models.py           # Data models (Pydantic)
│       ├── io.py               # File input/output
│       ├── validation.py       # Input validation logic
│       ├── compute.py          # Core algorithms
│       └── ui.py               # Gradio interface
├── tests/
│   ├── __init__.py
│   ├── test_compute.py         # Unit tests for algorithms
│   ├── test_validation.py      # Unit tests for validation
│   ├── test_io.py              # Unit tests for I/O
│   ├── test_integration.py     # End-to-end tests
│   └── fixtures/               # Test data files
│       ├── valid_pool.xlsx
│       ├── invalid_missing_col.xlsx
│       └── invalid_duplicates.xlsx
├── data/
│   └── example_pool.xlsx       # User-facing example
└── docker/
    ├── Dockerfile
    └── docker-compose.yml      # Optional
```

---

## 3. Data Models

### 3.1 Input Data Schema

Each row in the input spreadsheet represents a single library:

| Column Name | Type | Required | Constraints | Description |
|-------------|------|----------|-------------|-------------|
| `Project ID` | str | Yes | Non-empty, alphanumeric | Grouping identifier for sub-pools |
| `Library Name` | str | Yes | Non-empty, unique | Primary library identifier |
| `Final ng/ul` | float | Yes | > 0 | Concentration after normalization (ng/µl) |
| `Total Volume` | float | Yes | > 0 | Available sample volume (µl) |
| `Barcodes` | str | Yes | Non-empty, unique | Index/barcode sequence or ID |
| `Adjusted peak size` | float | Yes | > 0 | Average fragment length (base pairs) |
| `Empirical Library nM` | float | No | > 0 if provided | qPCR-measured molarity (overrides calculation) |
| `Target Reads (M)` | float | Yes | > 0 | Desired read allocation (millions) |

**Notes:**
- Column names are case-insensitive during matching
- Leading/trailing whitespace is stripped
- Uniqueness is enforced for `Library Name` and `Barcodes`

### 3.2 Internal Data Models

#### LibraryRecord
Represents raw input for a single library.

```python
from pydantic import BaseModel, Field

class LibraryRecord(BaseModel):
    project_id: str = Field(..., min_length=1)
    library_name: str = Field(..., min_length=1)
    final_ng_per_ul: float = Field(..., gt=0)
    total_volume_ul: float = Field(..., gt=0)
    barcode: str = Field(..., min_length=1)
    adjusted_peak_size_bp: float = Field(..., gt=0)
    empirical_nm: float | None = Field(None, gt=0)
    target_reads_m: float = Field(..., gt=0)
```

#### LibraryWithComputedFields
Extends `LibraryRecord` with calculated values.

```python
class LibraryWithComputedFields(LibraryRecord):
    computed_nm: float  # Calculated from ng/µl and bp
    effective_nm: float  # Either empirical_nm or computed_nm
    volume_in_pool_ul: float  # Volume to pipette
    pool_fraction: float  # Fraction of total pool (0-1)
    expected_reads: float | None  # If total reads specified
    flags: list[str]  # Validation warnings/errors
```

#### ProjectSummary
Aggregated metrics per project.

```python
class ProjectSummary(BaseModel):
    project_id: str
    library_count: int
    total_volume_ul: float
    pool_fraction: float  # Sum of library fractions (0-1)
    expected_reads_m: float | None
```

#### PoolingParams
Global parameters for pool calculation.

```python
class PoolingParams(BaseModel):
    desired_total_volume_ul: float = Field(..., gt=0)
    min_volume_ul: float = Field(1.0, gt=0)
    max_volume_ul: float | None = Field(None, gt=0)
    total_reads_m: float | None = Field(None, gt=0)
```

#### ValidationResult
Result of validation checks.

```python
class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str]  # Blocking errors
    warnings: list[str]  # Non-blocking warnings
    summary: dict[str, Any]  # e.g., {"num_libraries": 42, "num_projects": 3}
```

---

## 4. Core Algorithms

### 4.1 Effective Molarity Calculation

**Purpose:** Convert mass concentration to molar concentration.

**Formula:**
```
C_nM = (C_ng/µl × 10^6) / (MW_per_bp × L_bp)

where:
  C_ng/µl = concentration in ng/µl
  L_bp = fragment length in base pairs
  MW_per_bp = 660 g/mol (average for dsDNA)
  C_nM = molarity in nanomolar (nM)
```

**Logic:**
1. If `Empirical Library nM` is provided and > 0:
   - Set `effective_nm = empirical_nm`
2. Else:
   - Calculate `computed_nm = (final_ng_per_ul * 1e6) / (660 * adjusted_peak_size_bp)`
   - Set `effective_nm = computed_nm`
3. If `effective_nm` is NaN or ≤ 0:
   - Flag library as invalid

**Implementation:** `compute.py::compute_effective_molarity(df: pd.DataFrame) -> pd.DataFrame`

### 4.2 Weighted Pooling Algorithm

**Purpose:** Calculate pipetting volumes to achieve desired read proportions.

**Inputs:**
- List of libraries with effective molarities `C_i` (nM)
- Target read weights `w_i` (from `Target Reads (M)`)
- Desired total pool volume `V_pool` (µl)
- Min/max volume constraints

**Algorithm:**

1. **Calculate raw volume factors:**
   ```
   v_raw[i] = w_i / C_i
   ```
   *Intuition: Higher target reads or lower concentration → more volume needed*

2. **Sum total raw volume:**
   ```
   V_raw_total = Σ v_raw[i]
   ```

3. **Calculate scaling factor:**
   ```
   s = V_pool / V_raw_total
   ```

4. **Calculate final volumes:**
   ```
   V[i] = v_raw[i] × s
   ```

5. **Apply constraints and flag violations:**
   ```
   For each library i:
     if V[i] > total_volume_ul[i]:
       flags.append("Insufficient sample volume")
     if V[i] < min_volume_ul:
       flags.append("Below minimum pipetting volume")
     if max_volume_ul is set and V[i] > max_volume_ul:
       flags.append("Exceeds maximum pipetting volume")
   ```

6. **Calculate derived metrics:**
   ```
   # Fraction of pool contributed by library i
   f[i] = (V[i] × C[i]) / Σ(V[j] × C[j])

   # Expected reads for library i (if total_reads specified)
   if total_reads is not None:
     expected_reads[i] = total_reads × f[i]
   ```

**Special Cases:**
- **Equimolar pooling:** All `w_i` equal → all libraries contribute equal molecules
- **Insufficient volume:** Suggest reducing `V_pool` or diluting high-concentration libraries
- **Below minimum volume:** Suggest increasing `V_pool` or using more concentrated samples

**Implementation:** `compute.py::compute_pool_volumes(df: pd.DataFrame, params: PoolingParams) -> pd.DataFrame`

### 4.3 Project-Level Aggregation

**Purpose:** Summarize pool composition by project.

**Algorithm:**
```
For each unique project_id:
  library_count = count of libraries in project
  total_volume_ul = Σ V[i] for i in project
  pool_fraction = Σ f[i] for i in project
  expected_reads_m = Σ expected_reads[i] for i in project (if applicable)
```

**Output:** Table with one row per project.

**Implementation:** `compute.py::summarize_by_project(df: pd.DataFrame) -> pd.DataFrame`

---

## 5. Validation Rules

### 5.1 Column Presence Validation

**Rule:** All required columns must be present in input spreadsheet.

**Required Columns:**
- `Project ID`
- `Library Name`
- `Final ng/ul`
- `Total Volume`
- `Barcodes`
- `Adjusted peak size`
- `Target Reads (M)`

**Optional Columns:**
- `Empirical Library nM`

**Error Handling:**
- **Blocking:** Missing required column prevents all calculations
- **Error Message:** "Missing required columns: [col1, col2, ...]"

**Implementation:** `validation.py::validate_columns(df: pd.DataFrame) -> list[str]`

### 5.2 Data Type & Value Validation

**Per-Column Rules:**

| Column | Type Check | Value Check | Error Type |
|--------|-----------|-------------|------------|
| `Project ID` | str | non-empty | Blocking |
| `Library Name` | str | non-empty | Blocking |
| `Final ng/ul` | float | > 0 | Blocking |
| `Total Volume` | float | > 0 | Blocking |
| `Barcodes` | str | non-empty | Blocking |
| `Adjusted peak size` | float | > 0 | Blocking |
| `Empirical Library nM` | float or blank | > 0 if provided | Blocking |
| `Target Reads (M)` | float | > 0 | Blocking |

**Additional Checks:**
- **Warning:** Very low concentration (< 0.1 ng/µl) → "Library may be too dilute"
- **Warning:** Very high concentration (> 1000 ng/µl) → "Library may need dilution"
- **Warning:** Very small volume (< 5 µl) → "Insufficient volume for pooling"

**Error Message Format:**
```
Row {row_num}, {column}: {error_description}
Example: "Row 5, Final ng/ul: Value must be > 0, got -1.2"
```

**Implementation:** `validation.py::validate_rows(df: pd.DataFrame) -> tuple[list[str], list[str]]`

### 5.3 Uniqueness Validation

**Rule:** Certain fields must be unique across all libraries.

**Unique Fields:**
- `Library Name` - prevents ambiguity in results
- `Barcodes` - prevents demultiplexing conflicts

**Error Handling:**
- **Blocking:** Duplicates prevent calculations
- **Error Message:** "Duplicate {field} found: '{value}' in rows {row_list}"
- Example: "Duplicate Barcodes found: 'ATCG-GCTA' in rows 3, 7, 12"

**Implementation:** `validation.py::validate_uniqueness(df: pd.DataFrame) -> list[str]`

### 5.4 Validation Orchestration

**Process:**
1. Run column presence validation
   - If fails → return immediately (cannot proceed)
2. Run data type and value validation
   - Collect all errors and warnings
3. Run uniqueness validation
   - Add to error list
4. Return aggregated results

**Implementation:** `validation.py::run_all_validations(df: pd.DataFrame) -> ValidationResult`

---

## 6. User Interface Specification

### 6.1 UI Framework: Gradio

**Rationale:**
- Rapid development
- Built-in components (file upload, tables, downloads)
- Automatic API generation
- Simple deployment

### 6.2 UI Layout

#### Panel 1: File Upload
**Components:**
- File upload widget (accepts .xlsx)
- Status text: "No file uploaded" / "File loaded: {filename}" / "Error: {message}"

**Behavior:**
- On file upload → trigger validation
- Display validation results in Panel 3
- Enable/disable calculation button based on validation

#### Panel 2: Global Parameters
**Components:**
- Number input: "Desired total pool volume (µl)" [required]
  - Default: 50
  - Min: 1
  - Step: 0.1
- Number input: "Minimum per-library volume (µl)" [optional]
  - Default: 1.0
  - Min: 0.1
  - Step: 0.1
- Number input: "Maximum per-library volume (µl)" [optional]
  - Default: None (no limit)
  - Min: 0.1
  - Step: 0.1
- Number input: "Total reads (millions)" [optional]
  - Default: None
  - Min: 0.1
  - Step: 0.1
  - Info: "Used to calculate expected reads per library"

#### Panel 3: Validation Messages
**Components:**
- Accordion or collapsible sections:
  - **Errors** (red background, shown if any errors)
  - **Warnings** (yellow background, shown if any warnings)
  - **Summary** (blue background, always shown)

**Content Examples:**
- **Errors:**
  ```
  ❌ Missing required columns: Adjusted peak size
  ❌ Row 5, Final ng/ul: Value must be > 0, got -1.2
  ❌ Duplicate Barcodes found: 'ATCG-GCTA' in rows 3, 7
  ```
- **Warnings:**
  ```
  ⚠️ Row 8, Final ng/ul: Very low concentration (0.05 ng/µl) - library may be too dilute
  ```
- **Summary:**
  ```
  ✓ 24 libraries loaded
  ✓ 3 projects found: Project_A (10 libs), Project_B (8 libs), Project_C (6 libs)
  ```

#### Panel 4: Results
**Components:**
- Tabs:
  - **Tab 1: Library-Level Plan**
    - Gradio DataFrame component
    - Columns: Project ID, Library Name, Barcodes, Final ng/ul, Adjusted peak size, Empirical nM, Calculated nM, Effective nM, Target Reads (M), Volume to Add (µl), Pool Fraction (%), Expected Reads, Flags
    - Sortable, filterable
  - **Tab 2: Project Summary**
    - Gradio DataFrame component
    - Columns: Project ID, Library Count, Total Volume (µl), Pool Fraction (%), Expected Reads (M)

**Behavior:**
- Initially disabled/empty
- Populated after successful calculation
- Tables are interactive (sort, filter)

#### Panel 5: Export
**Components:**
- Button: "Download Pooling Plan (.xlsx)"
  - Initially disabled
  - Enabled after successful calculation
- File download component

**Behavior:**
- On click → generate Excel file
- Filename: `pooling_plan_YYYYMMDD_HHMMSS.xlsx`
- File contains 3 sheets: Libraries, Projects, Metadata

### 6.3 UI States & Transitions

| State | Trigger | UI Changes |
|-------|---------|------------|
| **Initial** | App launch | Upload enabled, params enabled, Calculate disabled, Results empty, Export disabled |
| **File Uploaded (Invalid)** | Upload with errors | Errors shown, Calculate disabled, Results empty, Export disabled |
| **File Uploaded (Valid)** | Upload without errors | Summary shown, Calculate enabled, Results empty, Export disabled |
| **Calculation Complete** | Click Calculate | Results populated, Export enabled |
| **Export Ready** | After calculation | Download button active |

### 6.4 Error Handling in UI

**File Upload Errors:**
- Corrupt file → "Error: Unable to read file. Please ensure it's a valid .xlsx file."
- Empty file → "Error: File contains no data."

**Calculation Errors:**
- No file uploaded → "Error: Please upload a file first."
- Invalid parameters → "Error: {parameter} must be > 0."

**Export Errors:**
- No results → "Error: Please calculate pool first."

---

## 7. File I/O Specifications

### 7.1 Input File Format (.xlsx)

**Structure:**
- Single workbook
- First sheet used by default (name doesn't matter)
- First row contains column headers
- Subsequent rows contain library data
- Empty rows (all cells blank) are ignored

**Example:**
| Project ID | Library Name | Final ng/ul | Total Volume | Barcodes | Adjusted peak size | Empirical Library nM | Target Reads (M) |
|------------|--------------|-------------|--------------|----------|-------------------|---------------------|------------------|
| Project_A | Lib_001 | 12.5 | 30 | ATCG-GGTA | 450 | | 10 |
| Project_A | Lib_002 | 8.3 | 25 | GCTA-ATCG | 380 | 35.2 | 10 |
| Project_B | Lib_003 | 15.7 | 40 | TTAA-CCGG | 520 | | 20 |

### 7.2 Output File Format (.xlsx)

**Workbook Structure:**

#### Sheet 1: PoolingPlan_Libraries
All columns from input plus computed fields:
- All original input columns
- `Calculated nM` (float, 1 decimal)
- `Effective nM` (float, 1 decimal)
- `Volume to Add (µl)` (float, 2 decimals)
- `Pool Fraction (%)` (float, 2 decimals)
- `Expected Reads` (float, 2 decimals, if applicable)
- `Flags` (string, comma-separated)

#### Sheet 2: PoolingPlan_Projects
Project-level summary:
- `Project ID` (string)
- `Library Count` (integer)
- `Total Volume (µl)` (float, 2 decimals)
- `Pool Fraction (%)` (float, 2 decimals)
- `Expected Reads (M)` (float, 2 decimals, if applicable)

#### Sheet 3: Metadata
Key-value pairs:
- `Generated At`: ISO 8601 timestamp
- `App Version`: Semantic version string
- `Input File`: Original filename
- `Total Pool Volume (µl)`: User-specified value
- `Minimum Volume (µl)`: User-specified value
- `Maximum Volume (µl)`: User-specified value (or "None")
- `Total Reads (M)`: User-specified value (or "None")
- `Number of Libraries`: Count
- `Number of Projects`: Count

**Formatting:**
- Number formats:
  - Integers: `0`
  - 1 decimal: `0.0`
  - 2 decimals: `0.00`
  - Percentages: `0.00%`
- Column widths: Auto-fit
- Header row: Bold, frozen pane

**Implementation:** `io.py::export_results_to_excel(...) -> bytes`

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Module: compute.py**

Test: `test_molarity_calculation_from_concentration`
- Input: concentration=10 ng/µl, fragment_size=500 bp, empirical=None
- Expected: computed_nm=30.30, effective_nm=30.30

Test: `test_empirical_molarity_overrides_calculated`
- Input: concentration=10 ng/µl, fragment_size=500 bp, empirical=50.0
- Expected: computed_nm=30.30, effective_nm=50.0

Test: `test_equimolar_pooling_equal_weights`
- Input: 2 libraries, C=[10nM, 20nM], w=[10, 10], V_pool=100µl
- Expected: V=[66.67µl, 33.33µl], f=[0.5, 0.5]

Test: `test_weighted_pooling_different_weights`
- Input: 2 libraries, C=[10nM, 10nM], w=[20, 10], V_pool=100µl
- Expected: V=[66.67µl, 33.33µl], f=[0.667, 0.333]

Test: `test_insufficient_volume_flagged`
- Input: Library with total_volume=5µl, calculated V=10µl
- Expected: Flag "Insufficient sample volume"

Test: `test_below_minimum_volume_flagged`
- Input: Library with calculated V=0.5µl, min_volume=1.0µl
- Expected: Flag "Below minimum pipetting volume"

**Module: validation.py**

Test: `test_missing_required_column_returns_error`
- Input: DataFrame without "Barcodes" column
- Expected: error="Missing required columns: Barcodes"

Test: `test_negative_concentration_returns_error`
- Input: Row with Final_ng_ul=-1.0
- Expected: error="Row X, Final ng/ul: Value must be > 0"

Test: `test_duplicate_barcode_returns_error`
- Input: Two rows with same barcode
- Expected: error="Duplicate Barcodes found: 'ATCG' in rows 2, 5"

Test: `test_valid_input_returns_no_errors`
- Input: Valid DataFrame
- Expected: is_valid=True, errors=[], warnings=[]

**Module: io.py**

Test: `test_load_valid_xlsx_returns_dataframe`
- Input: Valid .xlsx file
- Expected: DataFrame with correct shape and columns

Test: `test_export_creates_valid_excel_file`
- Input: Library and project DataFrames
- Expected: Excel file with 3 sheets, correct data

### 8.2 Integration Tests

Test: `test_full_pipeline_with_valid_input`
1. Load `tests/fixtures/valid_pool.xlsx`
2. Validate (expect success)
3. Compute molarity
4. Compute volumes
5. Summarize projects
6. Export to Excel
7. Re-load exported file
8. Assert values match expected

### 8.3 Test Fixtures

**File: `tests/fixtures/valid_pool.xlsx`**
- 10 libraries
- 3 projects
- Mix of empirical and calculated molarities
- All validation rules pass

**File: `tests/fixtures/invalid_missing_column.xlsx`**
- Missing "Adjusted peak size" column

**File: `tests/fixtures/invalid_duplicate_barcode.xlsx`**
- Two libraries with same barcode

### 8.4 Coverage Goals

- Core algorithms (compute.py): >90%
- Validation logic (validation.py): >90%
- I/O functions (io.py): >80%
- UI handlers (ui.py): >50% (UI testing is challenging)

---

## 9. Deployment

### 9.1 Local Development

**Setup:**
```bash
# Clone repository
cd pooling_calculator

# Install uv (if not already installed)
# Windows:
# Download from https://github.com/astral-sh/uv

# Create virtual environment and install dependencies
uv sync

# Run app
uv run python -m pooling_calculator.ui
```

**Access:** http://localhost:7860

### 9.2 Docker Deployment

**Build:**
```bash
cd pooling_calculator
docker build -t pooling-calculator:latest -f docker/Dockerfile .
```

**Run:**
```bash
docker run -p 7860:7860 pooling-calculator:latest
```

**Access:** http://localhost:7860

**Docker Compose (optional):**
```bash
docker-compose -f docker/docker-compose.yml up
```

### 9.3 Server Deployment

**Requirements:**
- Docker installed
- Exposed port (e.g., 7860 or 80/443 with reverse proxy)

**Recommended Setup:**
1. Nginx reverse proxy for HTTPS
2. Docker container running Gradio app
3. Firewall rules to restrict access if needed

**Example Nginx Config:**
```nginx
server {
    listen 80;
    server_name pooling-calculator.yourdomain.com;

    location / {
        proxy_pass http://localhost:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 10. Non-Functional Requirements

### 10.1 Performance

**Requirements:**
- Process up to 2,000 libraries in < 5 seconds
- UI responsiveness: All interactions < 100ms (excluding file I/O)
- Excel export: < 2 seconds for typical dataset (100 libraries)

**Optimization Strategies:**
- Use vectorized pandas operations (avoid Python loops)
- Lazy evaluation where possible
- Progress indicators for long operations

### 10.2 Robustness

**Error Handling:**
- All user-facing errors must have clear, actionable messages
- No cryptic stack traces shown to users
- Log detailed errors for debugging

**Edge Cases:**
- Empty input file → friendly error message
- Single library → still calculate (pool of 1)
- Extreme values (very high/low concentrations) → warnings but not blocking

**Data Validation:**
- All inputs validated before calculation
- Type checking at runtime (Pydantic models)
- Graceful handling of malformed files

### 10.3 Usability

**Principles:**
- Minimize clicks to complete task
- Clear visual feedback for all actions
- Error messages guide user to fix
- Example data provided

**Accessibility:**
- High contrast for readability
- Clear labels for all inputs
- Logical tab order

### 10.4 Maintainability

**Code Quality:**
- Follow best practices from CLAUDE.md
- Comprehensive docstrings
- Type hints on all functions
- Unit tests for core logic

**Versioning:**
- Semantic versioning (MAJOR.MINOR.PATCH)
- Changelog maintained
- Version included in exports

### 10.5 Reproducibility

**Scientific Reproducibility:**
- All constants documented (e.g., 660 g/mol/bp)
- Version and timestamp in outputs
- Identical inputs → identical outputs (deterministic)

**Software Reproducibility:**
- Lockfile for dependencies (uv.lock)
- Docker for environment consistency
- CI/CD for regression testing

---

## 11. Future Enhancements (Post-MVP)

### 11.1 Phase 2 Features

**Priority: High**
1. **CSV Input Support**
   - Accept .csv in addition to .xlsx
   - Auto-detect delimiter

2. **Liquid Handler Export**
   - Generate worklists for Hamilton, Tecan, etc.
   - Customizable format templates

3. **Dilution Calculator**
   - Suggest dilutions for overly concentrated libraries
   - Calculate dilution volumes and factors

**Priority: Medium**
4. **Custom Sub-pools**
   - Allow user-defined groupings beyond Project ID
   - Per-group weighting (e.g., "Project A should get 2x reads")

5. **Batch Processing**
   - Upload multiple files → generate multiple pools
   - Useful for core facilities

6. **Parameter Presets**
   - Save/load common parameter sets
   - Share presets between users

**Priority: Low**
7. **Advanced Visualization**
   - Interactive pie charts (pool composition)
   - Bar charts (reads per library/project)
   - Export charts as images

8. **API Mode**
   - REST API endpoints for LIMS integration
   - Programmatic access (no UI)

9. **Multi-step Pooling**
   - Hierarchical pooling (sub-pools → master pool)
   - Preserve balance across all levels

### 11.2 Infrastructure Improvements

1. **CI/CD Pipeline**
   - Automated testing on push
   - Docker image builds
   - Deployment to staging/production

2. **Logging & Monitoring**
   - Structured logging
   - Error tracking (e.g., Sentry)
   - Usage analytics (privacy-respecting)

3. **Authentication (if deployed publicly)**
   - User accounts
   - Usage quotas
   - API keys for programmatic access

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **Equimolar pooling** | Combining libraries so each contributes equal number of molecules |
| **Weighted pooling** | Combining libraries in custom proportions (e.g., 2:1) |
| **NGS** | Next-Generation Sequencing; high-throughput DNA sequencing |
| **Library** | A prepared DNA sample ready for sequencing |
| **Barcode / Index** | Short DNA sequence used to identify samples after sequencing |
| **Demultiplexing** | Separating mixed sequencing reads by barcode |
| **Fragment length** | Average size of DNA molecules in a library (base pairs) |
| **Molarity** | Concentration in moles per liter (or nanomoles per liter) |
| **Read depth** | Number of sequencing reads for a given sample |
| **Sub-pool** | A group of libraries pooled together (e.g., by project) |
| **Pipetting volume** | Amount of liquid to transfer (microliters) |

---

## 13. References

### Scientific
- DNA molecular weight: ~660 g/mol per base pair (average for dsDNA)
- Avogadro's number: 6.022 × 10²³ molecules/mol

### Technical Documentation
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Gradio Documentation](https://gradio.app/docs/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [uv Documentation](https://github.com/astral-sh/uv)

### Project Files
- [CLAUDE.md](./CLAUDE.md) - AI assistant guidance
- [TODO.md](./TODO.md) - Implementation checklist
- [README.md](./README.md) - User documentation

---

## 14. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-16 | Initial | Complete specification created |

---

**End of Specification**
