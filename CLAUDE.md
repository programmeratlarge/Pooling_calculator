# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Pooling calculator** is a Next-Generation Sequencing (NGS) library pooling utility that calculates precise pipetting volumes to achieve equimolar (or weighted) pooling across samples. The calculator takes per-library concentration and fragment length data and computes volumes needed so each library contributes the desired number of molecules to the final sequencing pool.

In practice, it takes per-library concentration and size information and converts that into precise pipetting volumes, ensuring that the final pool is equimolar (or otherwise "weighted" according to user-defined targets) across all samples. For each input library, users typically provide: (1) measured concentration (e.g., ng/µl from Qubit), (2) average fragment length (from Bioanalyzer or Fragment Analyzer), and sometimes (3) directly measured molarity from qPCR. The calculator converts mass concentration into molar concentration using fragment length, then determines how much volume of each library must be taken for equimolar pooling or specified read proportions.

The project focuses on advanced sub-pool management, allowing users to combine pre-pooled sample groups while preserving equal representation across all underlying samples. This is critical for high-plex experiments where dozens or hundreds of libraries need balanced read depth.

# Pooling Calculator – Technical Specification

## 1. Overview

**Pooling calculator** is a Python-based Next-Generation Sequencing (NGS) library pooling utility that calculates precise pipetting volumes to achieve equimolar (or weighted) pooling across samples. It consumes a spreadsheet of library metadata (concentrations, fragment sizes, barcodes, etc.), validates the inputs, computes effective molar concentrations, and outputs the volumes each library should contribute to the final sequencing pool.

The primary goals are:

* Automate error-prone molarity and pooling calculations.
* Support weighted pooling via per-library target read counts.
* Provide visibility into sub-pools (e.g., by project) so that high-plex designs remain balanced.
* Run locally in a Windows + Python environment, with optional Dockerized deployment and simple web UI (e.g., Gradio).

---

## 2. Target Runtime Environment

* **OS**: Windows 10/11 (primary development and usage environment).
* **Editor**: Cursor (VS Code fork); project structure should be friendly to VS Code/Cursor (e.g., `.vscode` tasks optional).
* **Language**: Python 3.11+ (managed via `uv`).
* **Dependency Management**: `uv` (for creating virtual environments and managing dependencies).
* **UI Framework**: Gradio (preferred) for a local browser-based interface.
* **Containerization**: Docker for packaging a reproducible environment and deploying the app on a server.

---

## 3. Core Concepts

### 3.1 Library-Level Inputs

Each row in the input spreadsheet represents a library and must contain the following columns:

* `Project ID` (str)

  * Non-empty alphanumeric string.
  * Used for grouping and sub-pool reporting.
* `Library Name` (str)

  * Non-empty, unique alphanumeric string.
  * Acts as the primary identifier for the library.
* `Final ng/ul` (float)

  * Non-null, positive.
  * Library concentration in ng/µl after any prior normalization.
* `Total Volume` (float)

  * Non-null, positive.
  * Available volume of this library in µl.
* `Barcodes` (str)

  * Non-null, unique string.
  * Represents index or barcode identifier; uniqueness prevents demultiplexing conflicts.
* `Adjusted peak size` (float)

  * Non-null, positive.
  * Average/peak fragment length in base pairs.
* `Empirical Library nM` (float or blank)

  * Optional; if provided, overrides calculated molarity.
* `Target Reads (M)` (float)

  * Non-null, positive.
  * Desired relative read allocation in millions of reads; forms the basis for weighted pooling.

### 3.2 Effective Molarity Calculation

For each library:

1. If `Empirical Library nM` is provided and > 0:

   * Use this value as the **effective molarity**.

2. Otherwise, compute molarity from `Final ng/ul` and `Adjusted peak size`:

   * Let:

     * C_ng/µl = Final ng/ul
     * L_bp = Adjusted peak size (bp)
     * Average molecular weight per base pair for dsDNA ≈ 660 g/mol.

   * Convert ng/µl to nM:

     C_nM = (C_ng/µl * 10^6) / (660 * L_bp)

   * This value becomes the **effective molarity** for that library.

If effective molarity is zero or NaN after calculation, the library is flagged as invalid.

### 3.3 Weighting by Target Reads

The `Target Reads (M)` column defines the relative contribution of each library to the final pool:

* Define w_i = `Target Reads (M)` for library i.
* The algorithm ensures that the number of molecules contributed by each library is proportional to ( w_i ).
* If all libraries have the same `Target Reads (M)`, this reduces to equimolar pooling.

---

## 4. Functional Requirements

### 4.1 File Input & Parsing

* Users can load a spreadsheet via:

  * File browser selection.
  * Drag-and-drop (supported by the UI framework).
* Supported formats:

  * `.xlsx` (primary).
  * Optionally `.csv` (configurable).
* App reads the first sheet by default, or a specified sheet:

  * Config: `DEFAULT_SHEET_NAME` (optional).
* Rows with all required fields blank should be ignored; partial rows must be validated and either accepted or flagged.

### 4.2 Validation Logic

Validation runs immediately after file load and before any calculations.

#### 4.2.1 Column Presence

* All required columns must be present (case-insensitive match, but normalized internally).
* If any required column is missing:

  * Show blocking error (no calculations performed).
  * Error message should list missing columns.

#### 4.2.2 Data Type & Value Constraints

For each row:

* `Project ID`

  * Not null/empty.
  * Alphanumeric check (allow `_`, `-`, space as configurable).
* `Library Name`

  * Not null/empty.
  * Must be unique across all rows.
* `Final ng/ul`

  * Must parse as float.
  * Must be > 0.
* `Total Volume`

  * Must parse as float.
  * Must be > 0.
* `Barcodes`

  * Not null/empty.
  * Must be unique across all rows.
* `Adjusted peak size`

  * Must parse as float.
  * Must be > 0.
* `Empirical Library nM`

  * If not blank, must parse as float and be > 0.
* `Target Reads (M)`

  * Must parse as float.
  * Must be > 0.

Validation behavior:

* If any blocking error occurs (e.g., missing required field, bad data type, negative/zero where not allowed):

  * Display detailed error messages in a text area.
  * Prevent downstream calculations.
* Non-blocking warnings (e.g., extremely high or low concentrations, very small `Total Volume`) should be surfaced but do not necessarily prevent calculations unless thresholds are exceeded.

#### 4.2.3 Uniqueness

* `Library Name`: enforce uniqueness.
* `Barcodes`: enforce uniqueness.
* If duplicates are found:

  * List duplicates and corresponding rows.
  * Treat as blocking errors.

### 4.3 Pooling Computation

#### 4.3.1 Inputs to Computation Engine

* Cleaned and validated table of libraries.
* User-specified global parameters (via UI) such as:

  * `Desired total pool volume (µl)` – required.
  * `Minimum per-library pipetting volume (µl)` – optional; default e.g. 1.0 µl.
  * `Maximum per-library pipetting volume (µl)` – optional.
  * Optional `Final pool target molarity (nM)` – currently informational; primary computation is volume distribution.

#### 4.3.2 Algorithm (Weighted Pooling)

1. For each library i:

   * Determine effective molarity C_i (nM) as per section 3.2.
   * Let w_i = `Target Reads (M)`.

2. Compute an unscaled volume factor for each library:

   v_i^raw = w_i / C_i

   * Intuition: To achieve higher read proportion with lower concentration, volume must increase.

3. Compute total raw volume factor:

   V_raw,total = sum for all i ( v_i^raw)

4. Scale to desired total pool volume ( V_{\text{pool}} ) (user input):

   s = V_pool / V_raw,total

5. Final volumes for each library:

   V_i = v_i^raw cdot s

6. Sanity checks:

   * For each library:

     * Ensure V_i <= `Total Volume`.
     * Ensure V_i >= `Minimum per-library pipetting volume`, if set.
   * If violations occur:

     * Flag libraries and mark as “insufficient volume” or “below pipetting limit”.
     * Optionally suggest:

       * Reducing total pool volume.
       * Decreasing target reads for problematic libraries.
       * Performing an intermediate dilution step.

7. Derived metrics (for reporting):

   * Fraction of pool contributed by each library:
     f_i = (V_i cdot C_i) / (sum for all j (V_j cdot C_j))
   * Expected read fraction (same as ( f_i ), assuming proportional to molecules).
   * Expected reads per library given a user-specified `Total reads` (optional UI input).

#### 4.3.3 Sub-Pool Management (Project-Level Aggregation)

Using `Project ID` as a natural grouping key:

* Aggregate volumes and expected reads per project:

  * Total volume from project p:
    V_p = sum for i in p (V_i)
  * Project-level fraction of pool:
    f_p = sum for i in p (f_i)
* Outputs:

  * Table summarizing:

    * `Project ID`
    * Number of libraries
    * Total volume contributed
    * Fraction of total pool
    * Expected total reads (if total reads provided).

Future extensibility:

* Ability to define custom sub-pools (e.g., additional column or separate config).
* Option to specify per-project weights (e.g., “Project A should get 2x reads relative to Project B”).

### 4.4 Outputs

#### 4.4.1 On-Screen Tables

* **Per-library pooling plan**:

  * `Project ID`
  * `Library Name`
  * `Barcodes`
  * `Final ng/ul`
  * `Adjusted peak size`
  * `Empirical Library nM` (if any)
  * `Calculated nM`
  * `Effective nM` (chosen molarity)
  * `Target Reads (M)`
  * `Calculated Volume (µl)` to add to pool
  * `Fraction of pool (%)`
  * `Expected Reads (if total reads provided)`
  * `Flags` (e.g., “Insufficient volume”, “Below min pipet volume”)

* **Project-level summary**:

  * `Project ID`
  * `Number of Libraries`
  * `Total Volume (µl)`
  * `Fraction of Pool (%)`
  * `Expected Reads (M)`

#### 4.4.2 Downloadable Files

* Export options:

  * `.xlsx` with separate sheets:

    * `PoolingPlan_Libraries`
    * `PoolingPlan_Projects`
    * `InputSummary` / `ValidationLog` (optional).
  * `.csv` exports for core tables (optional).

* Timestamps and project identifiers should be included in filenames, e.g.:

  * `pooling_plan_<YYYYMMDD_HHMMSS>.xlsx`

### 4.5 UI/UX Requirements (Gradio or Similar)

* Main layout:

  1. **File upload panel**

     * Drag-and-drop area + file browser button.
  2. **Global parameters panel**

     * Numeric inputs for:

       * Desired total pool volume (µl).
       * Minimum per-library volume (µl).
       * Maximum per-library volume (µl).
       * Optional total reads (M).
  3. **Validation & messages**

     * Scrollable text area to show:

       * Errors (blocking).
       * Warnings (non-blocking).
       * Summary: number of libraries, projects, etc.
  4. **Results**

     * Tabbed interface for:

       * Library-level output table.
       * Project-level summary table.
  5. **Export controls**

     * Buttons for:

       * “Download pooling plan (xlsx)”
       * Optional “Download CSVs”

* States:

  * Before file upload: disabled calculation controls and empty tables.
  * After successful validation: enable “Calculate Pool” button.
  * After calculation: show tables and export options.

---

## 5. Architecture & Code Organization

### 5.1 Project Structure

Example layout:

```text
pooling_calculator/
  pyproject.toml        # uv-managed project definition
  README.md
  CLAUDE.md             # development instructions / spec
  src/
    pooling_calculator/
      __init__.py
      config.py         # default parameters, thresholds
      models.py         # dataclasses / Pydantic models for Library, Project, etc.
      io.py             # spreadsheet parsing and serialization
      validation.py     # validation routines
      compute.py        # molarity + pooling algorithms
      ui.py             # Gradio app definitions
      logging_utils.py  # logging helpers (optional)
  tests/
    test_io.py
    test_validation.py
    test_compute.py
  docker/
    Dockerfile
  .gitignore
```

### 5.2 Data Models

Use dataclasses or Pydantic models for strong typing and validation.

* `LibraryRecord`

  * Fields: project_id, library_name, final_ng_per_ul, total_volume_ul, barcode, adjusted_peak_size_bp, empirical_nm (optional), target_reads_m, etc.
* `LibraryWithComputedFields`

  * Extends `LibraryRecord` with:

    * computed_nm
    * effective_nm
    * volume_in_pool_ul
    * pool_fraction
    * expected_reads
    * flags (list of strings)
* `ProjectSummary`

  * project_id, library_count, total_volume_ul, pool_fraction, expected_reads_m

### 5.3 Modules

* `io.py`

  * Functions:

    * `load_spreadsheet(path_or_bytes) -> pd.DataFrame`
    * `export_results_to_excel(...) -> bytes or file path`
* `validation.py`

  * Functions:

    * `validate_columns(df) -> list[Error]`
    * `validate_rows(df) -> list[Error]`
    * `validate_uniqueness(df) -> list[Error]`
    * `run_all_validations(df) -> (clean_df, errors, warnings)`
* `compute.py`

  * Core algorithm functions:

    * `compute_effective_molarity(df) -> df_with_nm`
    * `compute_pool_volumes(df, pool_params) -> df_with_volumes`
    * `summarize_by_project(df) -> project_summary_df`
* `ui.py`

  * Gradio interface functions:

    * `build_app() -> gr.Blocks`
    * Main entrypoint: `if __name__ == "__main__": build_app().launch(...)`

---

## 6. Non-Functional Requirements

* **Robustness**:

  * Must handle spreadsheets with hundreds to thousands of libraries.
  * Clear error messages whenever computation cannot proceed.
* **Performance**:

  * Typical dataset (≤ 2,000 libraries) should process in under a few seconds.
* **Reproducibility**:

  * Versions of assumptions (e.g., 660 g/mol/bp) encoded as constants in `config.py`.
  * Include app version string and timestamp in exports.
* **Testability**:

  * Core logic (`compute_effective_molarity`, `compute_pool_volumes`) must be unit tested.
  * Validation functions should have tests covering edge cases (missing columns, negative values, duplicates).
* **Portability**:

  * App must run via:

    * `uv run python -m pooling_calculator.ui`
    * `docker run ...` for containerized environment.

---

## 7. Docker & Deployment

### 7.1 Dockerfile Requirements

* Base image: official Python 3.11 (or similar).
* Install system-level dependencies (if any) used by Pandas / Excel writers.
* Copy project, install via `uv` or `pip` (depending on deployment approach).
* Expose port (e.g., `7860`) for Gradio.
* Set entrypoint to start the app, e.g.:

```bash
uv run python -m pooling_calculator.ui
```

### 7.2 Deployment Usage

* Local:

  * User runs `uv sync` to install dependencies.
  * Then `uv run python -m pooling_calculator.ui`.
* Server:

  * Build Docker image.
  * Run container with published port.
  * Users connect via browser to server:port.

---

## 8. Testing & QA Plan

* **Unit tests**:

  * Molarity calculation with known inputs.
  * Volume scaling for simple test cases (e.g., two libraries with known concentrations and target reads).
* **Validation tests**:

  * Missing required column → blocking error.
  * Non-numeric `Final ng/ul` → blocking error.
  * Duplicate barcodes → blocking error.
* **Integration tests**:

  * Provide a small test spreadsheet as fixture.
  * Run full pipeline: load → validate → compute → export.
* **Regression tests**:

  * Fixed input → stable output (volumes, fractions) even after refactoring.

---

This specification should give Claude Code a clear roadmap to:

1. Scaffold the Python project with `uv`.
2. Implement robust spreadsheet parsing and validation.
3. Implement the core pooling algorithms with clear, testable functions.
4. Build a minimal but functional Gradio UI.
5. Add Docker support for deployment.

---

## Working with Users: Core Principles

### Before starting, always read project plan for the full background

### 1. Establish Context First
When a user asks for help:
- Ask what they're trying to accomplish (understand the goal)
- Ask what error or behavior they're seeing (get actual error messages)

### 2. Diagnose Before Fixing (MOST IMPORTANT)

**DO NOT jump to conclusions and write lots of code before understanding the problem.**

Common mistakes to avoid:
- Writing defensive code with `isinstance()` checks before understanding root cause
- Adding try/except blocks that hide the real error
- Creating workarounds that mask the actual problem
- Making multiple changes at once (makes debugging impossible)

**Correct process:**
1. **Reproduce** - Get exact error messages, logs, commands
2. **Identify root cause** - Use error traces
3. **Verify understanding** - Explain what you think is happening and confirm with user
4. **Propose minimal fix** - Change one thing at a time
5. **Test and verify** - Confirm the fix works before moving on

### 3. Common Root Causes (Check These First)

Before writing any code, check these common issues:

**Docker Desktop Not Running** (Most common with `package_docker.py`)
- The script will fail with a generic uv warning about nested projects
- The real issue is Docker isn't running
- Users often get distracted by the uv warning (this was recently fixed in the script)
- **Always ask**: "Is Docker Desktop running?"

### 4. Help Users Help Themselves

Encourage users to:
- Read error messages carefully (especially logs)
- Test incrementally (don't deploy everything at once)

---

## Common Issues and Troubleshooting

### Issue 1: `package_docker.py` Fails

**Symptoms**: Script fails with uv warning about nested projects and perhaps an error message

**Root Cause (common)**: Docker Desktop is not running or a Docker mounts denied issue

**Diagnosis**:
1. Ask: "Is Docker Desktop running?"
2. Check: Can they run `docker ps` successfully?
3. Recent fix: The script now gives better error messages, but older versions were misleading

**Solution**: Start Docker Desktop, wait for it to fully initialize, then retry

**If the issue is a Mounts Denied error**: It fails to mount the /tmp directory into Docker as it doesn't have access to it. Going to Docker Desktop app, and adding the directory mentioned in the error to the shared paths (Settings → Resources → File Sharing) solved the problem for a user.

**Not the solution**: Changing uv project configurations (this is a red herring)

---

## Directory Structure

```
Pooling_calculator/
├── images/              # (planned)
└── data/               # (planned)
    └── example_pool.xlsx
```

Project is in early stages. Primary implementation will include:
- Input spreadsheet handling (Project ID, Library Name, concentrations, fragment lengths)
- Equimolar pooling calculations
- Sub-pool management and merging
- Volume and dilution calculations
- Exportable protocols for liquid handlers

---

## For Claude Code (AI Assistant)

When helping users:

0. **Prepare** - Read codebase and project plan to be fully briefed
1. **Establish context** - What's the goal?
2. **Get error details** - Actual messages, logs, console output
3. **Diagnose first** - Don't write code before understanding the problem
4. **Think incrementally** - One change at a time
5. **Verify understanding** - Explain what you think is wrong before fixing
6. **Keep it simple** - Avoid over-engineering solutions

**Remember**: Users are learning. The goal is to help them understand what went wrong and how to fix it, not just to make the error go away.

---

*This guide was created to help AI assistants (like Claude Code) effectively support users through the pooling calculator project. Last updated: December 2025*

# Claude Code Guidelines by Sabrina Ramonov

## Implementation Best Practices

### 0 — Purpose  

These rules ensure maintainability, safety, and developer velocity. 
**MUST** rules are enforced by CI; **SHOULD** rules are strongly recommended.

---

### 1 — Before Coding

- **BP-1 (MUST)** Ask the user clarifying questions.
- **BP-2 (SHOULD)** Draft and confirm an approach for complex work.  
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros and cons.

---

### 2 — While Coding

- **C-1 (MUST)** Name functions with existing domain vocabulary for consistency.  
- **C-2 (SHOULD NOT)** Introduce classes when small testable functions suffice.  
- **C-3 (SHOULD)** Prefer simple, composable, testable functions.
- **C-4 (SHOULD NOT)** Add comments except for critical caveats; rely on self‑explanatory code.
- **C-5 (SHOULD NOT)** Extract a new function unless it will be reused elsewhere, is the only way to unit-test otherwise untestable logic, or drastically improves readability of an opaque block.

---

### 3 — Testing

- **T-1 (MUST)** ALWAYS separate pure-logic unit tests from DB-touching integration tests.
- **T-2 (SHOULD)** Prefer integration tests over heavy mocking.  
- **T-3 (SHOULD)** Unit-test complex algorithms thoroughly.
- **T-4 (SHOULD)** Test the entire structure in one assertion if possible

---

### 4 — Database

- **D-1 No guidelines yet.

---

### 5 — Code Organization

- **O-1 No guidelines yet.

---

### 6 — Tooling Gates

- **G-1 No guidelines yet.

---

### 7 - Git

- **GH-1 (MUST**) Use Conventional Commits format when writing commit messages: https://www.conventionalcommits.org/en/v1.0.0
- **GH-2 (SHOULD NOT**) Refer to Claude or Anthropic in commit messages.

---

## Writing Functions Best Practices

When evaluating whether a function you implemented is good or not, use this checklist:

1. Can you read the function and HONESTLY easily follow what it's doing? If yes, then stop here.
2. Does the function have very high cyclomatic complexity? (number of independent paths, or, in a lot of cases, number of nesting if if-else as a proxy). If it does, then it's probably sketchy.
3. Are there any common data structures and algorithms that would make this function much easier to follow and more robust? Parsers, trees, stacks / queues, etc.
4. Are there any unused parameters in the function?
5. Are there any unnecessary type casts that can be moved to function arguments?
6. Is the function easily testable without mocking core features (e.g. sql queries, redis, etc.)? If not, can this function be tested as part of an integration test?
7. Does it have any hidden untested dependencies or any values that can be factored out into the arguments instead? Only care about non-trivial dependencies that can actually change or affect the function.
8. Brainstorm 3 better function names and see if the current name is the best, consistent with rest of codebase.

IMPORTANT: you SHOULD NOT refactor out a separate function unless there is a compelling need, such as:
  - the refactored function is used in more than one place
  - the refactored function is easily unit testable while the original function is not AND you can't test it any other way
  - the original function is extremely hard to follow and you resort to putting comments everywhere just to explain it

## Writing Tests Best Practices

When evaluating whether a test you've implemented is good or not, use this checklist:

1. SHOULD parameterize inputs; never embed unexplained literals such as 42 or "foo" directly in the test.
2. SHOULD NOT add a test unless it can fail for a real defect. Trivial asserts (e.g., expect(2).toBe(2)) are forbidden.
3. SHOULD ensure the test description states exactly what the final expect verifies. If the wording and assert don’t align, rename or rewrite.
4. SHOULD compare results to independent, pre-computed expectations or to properties of the domain, never to the function’s output re-used as the oracle.
5. SHOULD follow the same lint, type-safety, and style rules as prod code (prettier, ESLint, strict types).
6. SHOULD express invariants or axioms (e.g., commutativity, idempotence, round-trip) rather than single hard-coded cases whenever practical. 
7. Unit tests for a function should be grouped under `describe(functionName, () => ...`.
8. Use `expect.any(...)` when testing for parameters that can be anything (e.g. variable ids).
9. ALWAYS use strong assertions over weaker ones e.g. `expect(x).toEqual(1)` instead of `expect(x).toBeGreaterThanOrEqual(1)`.
10. SHOULD test edge cases, realistic input, unexpected input, and value boundaries.
11. SHOULD NOT test conditions that are caught by the type checker.

## Remember Shortcuts

Remember the following shortcuts which the user may invoke at any time.

### QNEW

When I type "qnew", this means:

```
Understand all BEST PRACTICES listed in CLAUDE.md.
Your code SHOULD ALWAYS follow these best practices.
```

### QPLAN
When I type "qplan", this means:
```
Analyze similar parts of the codebase and determine whether your plan:
- is consistent with rest of codebase
- introduces minimal changes
- reuses existing code
```

## QCODE

When I type "qcode", this means:

```
Implement your plan and make sure your new tests pass.
Always run tests to make sure you didn't break anything else.
```

### QCHECK

When I type "qcheck", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR code change you introduced (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
2. CLAUDE.md checklist Writing Tests Best Practices.
3. CLAUDE.md checklist Implementation Best Practices.
```

### QCHECKF

When I type "qcheckf", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR function you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
```

### QCHECKT

When I type "qcheckt", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR test you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Tests Best Practices.
```

### QUX

When I type "qux", this means:

```
Imagine you are a human UX tester of the feature you implemented. 
Output a comprehensive list of scenarios you would test, sorted by highest priority.
```

### QGIT

When I type "qgit", this means:

```
Add all changes to staging, create a commit, and push to remote.

Follow this checklist for writing your commit message:
- SHOULD use Conventional Commits format: https://www.conventionalcommits.org/en/v1.0.0
- SHOULD NOT refer to Claude or Anthropic in the commit message.
- SHOULD structure commit message as follows:
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]
- commit SHOULD contain the following structural elements to communicate intent: 
fix: a commit of the type fix patches a bug in your codebase (this correlates with PATCH in Semantic Versioning).
feat: a commit of the type feat introduces a new feature to the codebase (this correlates with MINOR in Semantic Versioning).
BREAKING CHANGE: a commit that has a footer BREAKING CHANGE:, or appends a ! after the type/scope, introduces a breaking API change (correlating with MAJOR in Semantic Versioning). A BREAKING CHANGE can be part of commits of any type.
types other than fix: and feat: are allowed, for example @commitlint/config-conventional (based on the Angular convention) recommends build:, chore:, ci:, docs:, style:, refactor:, perf:, test:, and others.
footers other than BREAKING CHANGE: <description> may be provided and follow a convention similar to git trailer format.
```
