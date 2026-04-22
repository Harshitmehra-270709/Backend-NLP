"""
Root conftest.py – makes the repo root importable as a Python package root.
This ensures `from app.X import Y` works in both local pytest runs and CI.
"""
import sys
from pathlib import Path

# Insert the repository root at the front of sys.path so pytest can find
# the `app` package without needing PYTHONPATH to be set manually.
sys.path.insert(0, str(Path(__file__).parent))
