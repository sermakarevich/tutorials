"""Notebook setup: `from openmetadata_tutorial import nb; ROOT = nb.setup()` in a notebook's first cell.

A notebook's first cell walks up to the folder holding pyproject.toml, puts src/ on
sys.path and imports this module; see notebooks/README.md for the exact cell.
"""

import os
from pathlib import Path

import pandas as pd

from openmetadata_tutorial.config import project_root


def setup() -> Path:
    """Make cwd the project root (so .env and relative paths work) and set display options."""
    root = project_root()
    os.chdir(root)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 140)
    pd.set_option("display.max_colwidth", 60)
    return root
