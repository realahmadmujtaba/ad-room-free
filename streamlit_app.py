"""Entry point for Streamlit Community Cloud.

Streamlit Cloud looks for a main file at the repo root; the real UI lives in
src/app.py.
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
runpy.run_path(str(Path(__file__).parent / "src" / "app.py"), run_name="__main__")
