# Pooling Calculator - Quick Start Guide

## Installation

### Prerequisites
- Python 3.11 or higher
- uv package manager

### Setup
```bash
# Clone the repository (if you haven't already)
cd Pooling_calculator

# Install dependencies
uv sync --dev

# Verify installation
uv run python -c "import pooling_calculator; print(f'Version: {pooling_calculator.__version__}')"
```

Expected output:
```
Version: 0.1.0
```

## Running the Application

### Method 1: Run as Module (Recommended)
```bash
uv run python -m pooling_calculator.ui
```

### Method 2: Run Directly
```bash
uv run python src/pooling_calculator/ui.py
```

### Method 3: Test Script
```bash
uv run python test_gradio.py
```

## Accessing the Application

Once started, the Gradio app will be available at:

**URL:** http://127.0.0.1:7860

Open this URL in your web browser to access the interface.

## Application Features (Current Demo)

The current version includes three tabs:

### 1. Welcome Tab
- Simple greeting interface
- Tests basic Gradio functionality
- Enter your name and get a personalized greeting

### 2. Molarity Calculator Tab
- Quick molarity calculation tool
- **Formula:** C_nM = (C_ng/µl × 10⁶) / (660 × L_bp)
- **Example:**
  - Input: 10 ng/µl concentration, 500 bp fragment size
  - Output: 30.30 nM

### 3. About Tab
- Project information
- Technology stack
- Development status

## Troubleshooting

### Port Already in Use Error
**Error:** `OSError: Cannot find empty port in range: 7860-7860`

This means port 7860 is already in use by another process (likely from a previous run).

**Solution:**

**On Windows:**
```bash
# Step 1: Find the process using port 7860
netstat -ano | findstr :7860

# Step 2: Kill the process (replace XXXXX with the PID from step 1)
taskkill /F /PID XXXXX
```

**On Linux/Mac:**
```bash
# Step 1: Find the process using port 7860
lsof -i :7860

# Step 2: Kill the process (replace XXXXX with the PID from step 1)
kill -9 XXXXX
```

**Alternative:** Modify `ui.py` to use a different port (change `server_port=7860` to another number like `7861`)

### Import Errors
If you get import errors, make sure you're running commands with `uv run`:
```bash
uv run python -m pooling_calculator.ui
```

### Virtual Environment
The `uv sync` command automatically creates a virtual environment in `.venv/`.
All dependencies are installed there.

## Next Steps

### For Users
- Wait for full implementation of pooling calculations
- Check [TODO.md](./TODO.md) for planned features

### For Developers
Continue with Phase 2 implementation:
1. Create `config.py` with constants
2. Create `models.py` with Pydantic data models
3. Implement core calculation functions

See [SPEC.md](./SPEC.md) for detailed technical specifications.

## Stopping the Application

Press `Ctrl+C` in the terminal where the app is running.

---

**Current Status:** ✅ Phase 1 Complete (Project Setup)
**Next Phase:** 🔄 Phase 2 (Core Data Models)
