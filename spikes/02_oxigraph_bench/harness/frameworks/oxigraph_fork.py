"""Oxigraph (Deepthought-Solutions fork) adapter.

Same code path as the stock oxigraph adapter — only the framework name and
the build provenance differ. The actual engine is whichever pyoxigraph is
installed in the active Python interpreter (run this adapter from the fork
venv to test the fork; from the main venv to test the stock release).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pyoxigraph

from . import oxigraph as _stock

NAME = "oxigraph_fork"


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    out = _stock.run(data_path, queries, scale)
    out["framework"] = NAME
    out["build"] = "Deepthought-Solutions/oxigraph @ 5c7feb9 (bugfix/optimizer)"
    out["pyoxigraph_version"] = getattr(pyoxigraph, "__version__", "unknown")
    return out
