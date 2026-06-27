"""Make ``pcs_core`` importable when pytest is run from repo root or ``python/``."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
_root = str(_PYTHON_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)
