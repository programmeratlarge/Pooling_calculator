# Development Guide - Pooling Calculator

## Working with the Virtual Environment

### Understanding `uv` and Virtual Environments

When you ran `uv sync`, it created a virtual environment in the `.venv/` folder. This keeps all project dependencies isolated from your system Python.

### Do I Need to Activate the Virtual Environment?

**Short Answer: No!** (if you use `uv run`)

There are two approaches:

#### Option 1: Use `uv run` (Recommended)
`uv run` automatically uses the `.venv` environment. You don't need to activate anything.

```bash
# Just use uv run for all commands
uv run python -m pooling_calculator.ui
uv run pytest
uv run python -c "import pooling_calculator"
```

#### Option 2: Manual Activation (Traditional Way)
If you prefer traditional activation:

**On Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**On Linux/Mac:**
```bash
source .venv/bin/activate
```

After activation, your prompt will show `(.venv)`:
```
(.venv) C:\Users\prm88\Documents\...\Pooling_calculator>
```

Then you can run commands without `uv run`:
```bash
python -m pooling_calculator.ui
pytest
```

To deactivate:
```bash
deactivate
```

### How to Verify You're Using the Correct Environment

```bash
# Check which Python is being used
uv run python -c "import sys; print(sys.executable)"

# Should output something like:
# C:\Users\prm88\Documents\Box\...\Pooling_calculator\.venv\Scripts\python.exe
```

### After Closing and Reopening Cursor/VS Code

When you reopen the project:

1. **If using `uv run`**: Nothing to do! Just use `uv run` commands as normal.

2. **If you activated manually before**: You'll need to activate again using one of the activation commands above.

3. **Cursor/VS Code should auto-detect**: Many IDEs automatically detect `.venv` and offer to use it. Check the bottom status bar for Python version indicator.

### Quick Status Check

Run this command anytime to verify your setup:

```bash
uv run python -c "
import sys
import pooling_calculator
print(f'Python: {sys.executable}')
print(f'Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')
print(f'Pooling Calculator: v{pooling_calculator.__version__}')
print('✓ Environment OK!')
"
```

Expected output:
```
Python: C:\Users\prm88\...\Pooling_calculator\.venv\Scripts\python.exe
Version: 3.11.x
Pooling Calculator: v0.1.0
✓ Environment OK!
```

---

## Common Development Commands

### Running the App
```bash
# Start the Gradio web interface
uv run python -m pooling_calculator.ui
```

### Running Tests (when we add them)
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/pooling_calculator

# Run specific test file
uv run pytest tests/test_compute.py
```

### Installing New Dependencies

```bash
# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Sync after editing pyproject.toml manually
uv sync
```

### Code Quality (optional, when configured)

```bash
# Format code with black
uv run black src/ tests/

# Lint with ruff
uv run ruff check src/ tests/
```

---

## IDE Setup (Cursor/VS Code)

### Selecting the Python Interpreter

1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
2. Type "Python: Select Interpreter"
3. Choose the one that shows `.venv` in the path:
   ```
   Python 3.11.x ('.venv': venv) .\\.venv\\Scripts\\python.exe
   ```

Once selected, the IDE will use this interpreter for:
- Running scripts
- Debugging
- IntelliSense/autocomplete
- Linting

### Terminal Integration

Cursor/VS Code can automatically activate the virtual environment in integrated terminals:
- **Settings** → Search "Python: Terminal Activate Environment"
- Should be enabled by default

---

## Troubleshooting

### "Module not found" errors

If you get import errors:

1. Verify you're using `uv run`:
   ```bash
   uv run python -m pooling_calculator.ui
   ```

2. Check the environment:
   ```bash
   uv run python -c "import sys; print(sys.prefix)"
   # Should show path to .venv
   ```

3. Re-sync dependencies:
   ```bash
   uv sync
   ```

### Virtual environment not found

If `.venv` folder is missing:

```bash
# Recreate it
uv sync
```

### Port 7860 already in use

See [QUICKSTART.md](./QUICKSTART.md) troubleshooting section.

---

## Best Practices

1. **Always use `uv run`** for consistency across team members
2. **Never commit `.venv/`** to git (already in .gitignore)
3. **Do commit `pyproject.toml`** so others can recreate environment
4. **Run `uv sync`** after pulling changes that update dependencies

---

**TIP:** Bookmark this file for quick reference when starting a development session!
