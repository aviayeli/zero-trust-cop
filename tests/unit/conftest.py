"""Shared access to the cop -> thief README regenerator.

`scripts/thief_readme.py` sits in the ops `scripts/` directory at the repo
root, which is NOT the importable `src/scripts` package, so it is loaded by
path rather than imported. Both thief-README test modules need it.
"""

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def regenerator():
    """Load `scripts/thief_readme.py` by path, once per session."""
    spec = importlib.util.spec_from_file_location(
        "thief_readme", PROJECT_ROOT / "scripts" / "thief_readme.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
