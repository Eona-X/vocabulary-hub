"""Oxigraph adapter — disk-backed RocksDB store via pyoxigraph."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from pyoxigraph import RdfFormat, Store

from _lib.rss import measure_peak_rss
from _lib.timing import time_best_of, time_once

NAME = "oxigraph"


def _fmt_for(path: Path) -> RdfFormat:
    if path.suffix in {".nt", ".n3"}:
        return RdfFormat.N_TRIPLES
    if path.suffix in {".ttl", ".turtle"}:
        return RdfFormat.TURTLE
    raise ValueError(f"Unsupported format: {path}")


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="oxigraph-bench-"))
    store_path = work / "store"

    try:
        # ---- bulk load (single timed run, with RSS) ----
        def _load() -> Store:
            s = Store(path=str(store_path))
            s.bulk_load(path=str(data_path), format=_fmt_for(data_path))
            return s

        store, load_t = time_once(_load)
        # close + reopen so query timing reflects steady-state, not load-warmed caches
        del store
        store = Store(path=str(store_path))

        # ---- per-query best-of-3 + p50/p95 (last result captured for row count) ----
        def make_runner(q: str):
            return lambda: list(store.query(q))

        query_results: dict[str, Any] = {}
        for qid, qtext in queries.items():
            last, t = time_best_of(make_runner(qtext), n=3, warmup=1, timeout_s=300.0)
            d = t.to_dict()
            d["row_count"] = len(last) if last is not None else 0
            query_results[qid] = d

        # ---- peak RSS for the whole load+query lifecycle, re-run cleanly ----
        store.flush()
        del store
        shutil.rmtree(store_path)

        def _full_lifecycle() -> None:
            s = Store(path=str(store_path))
            s.bulk_load(path=str(data_path), format=_fmt_for(data_path))
            for q in queries.values():
                list(s.query(q))
            s.flush()

        _, rss = measure_peak_rss(_full_lifecycle, interval_s=0.05)

        return {
            "framework": NAME,
            "scale": scale,
            "data": str(data_path),
            "load_s": load_t,
            "queries": query_results,
            "rss_peak_bytes": rss.peak_bytes,
            "rss_delta_bytes": rss.delta_bytes,
            "store_bytes_on_disk": sum(
                p.stat().st_size for p in store_path.rglob("*") if p.is_file()
            ),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)
