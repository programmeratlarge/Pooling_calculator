#!/usr/bin/env python
"""
Quick environment check script for Pooling Calculator.
Run this anytime to verify your development environment is set up correctly.

Usage:
    uv run python check_env.py
"""

import sys
from pathlib import Path

# Use ASCII characters for Windows compatibility
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"


def main():
    print("=" * 70)
    print("Pooling Calculator - Environment Check")
    print("=" * 70)
    print()

    # Check Python version
    print(f"{CHECK} Python Information:")
    print(f"  Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"  Executable: {sys.executable}")
    print()

    # Check if in virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

    if in_venv:
        print(f"{CHECK} Virtual Environment: ACTIVE")
        print(f"  Location: {sys.prefix}")

        # Check if it's the project's .venv
        expected_venv = Path.cwd() / ".venv"
        actual_venv = Path(sys.prefix)

        if expected_venv.resolve() == actual_venv.resolve():
            print(f"  Status: Using project's .venv {CHECK}")
        else:
            print(f"  Status: Using a different venv (not .venv) {WARN}")
            print(f"  Expected: {expected_venv}")
    else:
        print(f"{CROSS} Virtual Environment: NOT DETECTED")
        print("  This might be OK if you're using 'uv run'")
    print()

    # Check package installation
    print(f"{CHECK} Package Imports:")
    try:
        import pooling_calculator
        print(f"  pooling_calculator: v{pooling_calculator.__version__} {CHECK}")
    except ImportError as e:
        print(f"  pooling_calculator: FAILED {CROSS}")
        print(f"    Error: {e}")
        return False

    try:
        import gradio
        print(f"  gradio: v{gradio.__version__} {CHECK}")
    except ImportError:
        print(f"  gradio: FAILED {CROSS}")
        return False

    try:
        import pandas
        print(f"  pandas: v{pandas.__version__} {CHECK}")
    except ImportError:
        print(f"  pandas: FAILED {CROSS}")
        return False

    try:
        import pydantic
        print(f"  pydantic: v{pydantic.__version__} {CHECK}")
    except ImportError:
        print(f"  pydantic: FAILED {CROSS}")
        return False

    try:
        import openpyxl
        print(f"  openpyxl: v{openpyxl.__version__} {CHECK}")
    except ImportError:
        print(f"  openpyxl: FAILED {CROSS}")
        return False

    print()

    # Check project structure
    print(f"{CHECK} Project Structure:")
    required_paths = [
        ("pyproject.toml", "file"),
        ("src/pooling_calculator/__init__.py", "file"),
        ("src/pooling_calculator/ui.py", "file"),
        ("tests", "dir"),
        ("data", "dir"),
    ]

    all_present = True
    for path_str, path_type in required_paths:
        path = Path(path_str)
        if path_type == "file":
            exists = path.is_file()
        else:
            exists = path.is_dir()

        status = CHECK if exists else CROSS
        print(f"  {path_str}: {status}")
        if not exists:
            all_present = False

    print()

    # Final summary
    print("=" * 70)
    if all_present:
        print(f"{CHECK} ALL CHECKS PASSED - Environment is ready!")
        print()
        print("You can now run:")
        print("  uv run python -m pooling_calculator.ui")
    else:
        print(f"{CROSS} SOME CHECKS FAILED - Please review errors above")
        print()
        print("Try running:")
        print("  uv sync")
    print("=" * 70)

    return all_present


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
