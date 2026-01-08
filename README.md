![checkMyIndex](./header_image.png)

# Pooling calculator

Next-Generation Sequencing (NGS) library pooling utility that calculates precise pipetting volumes to achieve equimolar (or weighted) pooling across samples. The calculator takes per-library concentration and fragment length data and computes volumes needed so each library contributes the desired number of molecules to the final sequencing pool.

The project focuses on advanced sub-pool management, allowing users to combine pre-pooled sample groups while preserving equal representation across all underlying samples. This is critical for high-plex experiments where dozens or hundreds of libraries need balanced read depth.

## Live App

You can run the pooling calculator here:

👉 **[http://cbsugenomics2.biohpc.cornell.edu:7860/](http://cbsugenomics2.biohpc.cornell.edu:7860/)**

---

## What This App Does

This repository contains the code and configuration for the pooling calculator, which:

Features:
- ✅ Molarity conversion (ng/µl → nM)
- ✅ Weighted pooling calculations
- ✅ Sub-pool management by project
- ✅ Excel/CSV input and output
- ✅ Comprehensive validation
- ✅ Web-based UI
- ✅ Docker deployment support

Technology Stack:
- 🎯 Python 3.11+
- 🎯 Gradio for UI
- 🎯 Pandas for data processing
- 🎯 Pydantic for validation
- 🎯 uv for dependency management

---

## Quick Start

### Local Installation

1. **Install uv** (if not already installed):
   ```bash
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Pooling_calculator.git
   cd Pooling_calculator
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Run the application:**
   ```bash
   uv run python -m pooling_calculator.ui
   ```

5. **Open your browser** to http://localhost:7860

### Docker Deployment

Run with Docker Compose (recommended):

```bash
cd docker
docker-compose up -d
```

Or build and run directly:

```bash
docker build -f docker/Dockerfile -t pooling-calculator .
docker run -d -p 7860:7860 pooling-calculator
```

Access at http://localhost:7860

For detailed Docker deployment instructions, see [docker/README.md](docker/README.md).

---

## Usage Guide

### 1. Prepare Your Input File

Create an Excel (.xlsx) or CSV file with the following required columns:

| Column Name | Type | Description | Example |
|------------|------|-------------|---------|
| Project ID | Text | Project or sample group identifier | ProjectA |
| Library Name | Text | Unique library identifier | Lib001 |
| Final ng/ul | Number | Library concentration in ng/µl | 10.5 |
| Total Volume | Number | Available volume in µl | 25.0 |
| Barcodes | Text | Unique barcode/index sequence | ATCGATCG |
| Adjusted peak size | Number | Fragment length in base pairs | 500 |
| Empirical Library nM | Number (optional) | qPCR-measured molarity (overrides calculation) | 15.2 |
| Target Reads (M) | Number | Desired millions of reads for this library | 100 |

Example:
```csv
Project ID,Library Name,Final ng/ul,Total Volume,Barcodes,Adjusted peak size,Empirical Library nM,Target Reads (M)
ProjectA,Lib001,10.5,25.0,ATCGATCG,500,,100
ProjectA,Lib002,12.3,30.0,GCTAGCTA,550,,100
ProjectB,Lib003,8.7,20.0,TTAATTAA,480,,50
```

### 2. Upload and Configure

1. Upload your Excel/CSV file
2. Set pooling parameters:
   - **Desired Pool Volume**: Total volume for the final pool (e.g., 20 µl)
   - **Min Pipettable Volume**: Minimum accurate pipette volume (e.g., 0.5 µl)
   - **Max Volume per Library** (optional): Constraint on individual libraries
   - **Total Reads** (optional): Expected sequencing run output for read distribution

### 3. Calculate and Review

Click "Calculate Pooling Plan" to:
- Validate your input data
- Calculate effective molarities
- Compute pipetting volumes
- Generate project summaries

### 4. Download Results

Download the Excel file containing:
- **Libraries sheet**: Per-library volumes and fractions
- **Projects sheet**: Aggregated project statistics
- **Metadata sheet**: Parameters and timestamp

---

## Running Tests

Run the complete test suite:

```bash
uv run python -m pytest tests/ -v --cov=src/pooling_calculator
```

Run specific test modules:

```bash
# Unit tests
uv run python -m pytest tests/test_compute.py -v
uv run python -m pytest tests/test_validation.py -v

# Integration tests
uv run python -m pytest tests/test_integration.py -v
```

Current test coverage: **72%** (104 tests passing)

---

## Development

### Project Structure

```
Pooling_calculator/
├── src/pooling_calculator/    # Main application code
│   ├── compute.py              # Molarity and pooling calculations
│   ├── validation.py           # Input validation logic
│   ├── io.py                   # File I/O operations
│   ├── models.py               # Data models (Pydantic)
│   ├── ui.py                   # Gradio web interface
│   └── config.py               # Configuration and constants
├── tests/                      # Test suite
│   ├── test_compute.py         # Computation tests (26)
│   ├── test_validation.py      # Validation tests (28)
│   ├── test_io.py              # I/O tests (17)
│   ├── test_models.py          # Model tests (26)
│   └── test_integration.py     # End-to-end tests (7)
├── docker/                     # Docker configuration
│   ├── Dockerfile              # Multi-stage build
│   ├── docker-compose.yml      # Compose configuration
│   └── README.md               # Docker deployment guide
└── pyproject.toml              # Project dependencies (uv)
```

### Adding Features

1. Write tests first (TDD approach)
2. Implement the feature
3. Run tests to verify
4. Update documentation

### Code Style

Follow the guidelines in [CLAUDE.md](CLAUDE.md):
- Keep functions simple and testable
- Avoid premature abstraction
- Use type hints
- Write clear docstrings

---

## Update History

| Version | Date       | Description                                                       |
|--------:|------------|-------------------------------------------------------------------|
| v0.2.0  | 2025-12-17 | Full implementation: Core functionality, UI, tests, Docker support |
| v0.1.0  | 2025-12-12 | Initial commit.                                                   |
