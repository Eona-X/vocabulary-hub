"""maplib in-memory adapter (Polars + Arrow core).

Only the in-memory `Model` is benchmarked; the disk-backed variant requires
the proprietary `storage_folder` parameter and is excluded by ADR-000.
"""
from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import maplib

from _lib.rss import measure_peak_rss
from _lib.timing import time_best_of, time_once

NAME = "maplib"


def _fmt_for(path: Path) -> str:
    return {".nt": "ntriples", ".ttl": "turtle"}[path.suffix]


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    m = maplib.Model()

    def _load() -> maplib.Model:
        m.read(file_path=str(data_path), format=_fmt_for(data_path), parallel=True)
        return m

    _, load_t = time_once(_load)

    query_results: dict[str, Any] = {}
    for qid, qtext in queries.items():
        def _runq(q=qtext):
            res = m.query(q)
            # res is a polars.DataFrame; .height is the row count (verified)
            return int(getattr(res, "height", None) or len(res))

        last, t = time_best_of(_runq, n=3, warmup=1, timeout_s=300.0)
        d = t.to_dict()
        d["row_count"] = int(last) if last is not None else 0
        query_results[qid] = d

    del m
    gc.collect()

    def _full_lifecycle() -> None:
        m2 = maplib.Model()
        m2.read(file_path=str(data_path), format=_fmt_for(data_path), parallel=True)
        for q in queries.values():
            r = m2.query(q)
            try:
                len(r)
            except TypeError:
                list(r)

    _, rss = measure_peak_rss(_full_lifecycle, interval_s=0.05)

    return {
        "framework": NAME,
        "scale": scale,
        "data": str(data_path),
        "load_s": load_t,
        "queries": query_results,
        "rss_peak_bytes": rss.peak_bytes,
        "rss_delta_bytes": rss.delta_bytes,
        "version": getattr(maplib, "__version__", "0.20.18"),
    }
