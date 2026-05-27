"""rdflib adapter — pure-Python in-memory baseline."""
from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import rdflib

from _lib.rss import measure_peak_rss
from _lib.timing import time_best_of, time_once

NAME = "rdflib"


def _fmt_for(path: Path) -> str:
    return {".nt": "nt", ".ttl": "turtle"}[path.suffix]


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    # ---- load ----
    g = rdflib.Graph()

    def _load() -> rdflib.Graph:
        g.parse(str(data_path), format=_fmt_for(data_path))
        return g

    _, load_t = time_once(_load)

    # ---- queries: best-of-3, p50/p95 ----
    query_results: dict[str, Any] = {}
    for qid, qtext in queries.items():
        def _runq(q=qtext):
            return sum(1 for _ in g.query(q))
        last, t = time_best_of(_runq, n=3, warmup=1, timeout_s=300.0)
        d = t.to_dict()
        d["row_count"] = int(last) if last is not None else 0
        query_results[qid] = d

    # ---- peak RSS for a clean full lifecycle ----
    del g
    gc.collect()

    def _full_lifecycle() -> None:
        g2 = rdflib.Graph()
        g2.parse(str(data_path), format=_fmt_for(data_path))
        for q in queries.values():
            list(g2.query(q))

    _, rss = measure_peak_rss(_full_lifecycle, interval_s=0.05)

    return {
        "framework": NAME,
        "scale": scale,
        "data": str(data_path),
        "load_s": load_t,
        "queries": query_results,
        "rss_peak_bytes": rss.peak_bytes,
        "rss_delta_bytes": rss.delta_bytes,
        "version": rdflib.__version__,
    }
