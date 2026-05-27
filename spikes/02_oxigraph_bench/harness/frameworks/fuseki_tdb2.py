"""Apache Jena Fuseki + TDB2 adapter.

Uses the bundled `tdb2.tdbloader` (shaded inside fuseki-server.jar) for bulk-load,
then runs fuseki-server over HTTP for queries. RSS is sampled on the JVM PID,
not the Python parent.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from _lib.rss import _PeakSampler
from _lib.timing import time_best_of, time_once

NAME = "fuseki_tdb2"

SPIKE_DIR = Path(__file__).resolve().parents[2]
FUSEKI_HOME = SPIKE_DIR / ".cache" / "apache-jena-fuseki-5.2.0"
FUSEKI_JAR = FUSEKI_HOME / "fuseki-server.jar"
FUSEKI_SCRIPT = FUSEKI_HOME / "fuseki-server"

DATASET = "ds"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status < 500:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    raise TimeoutError(f"Fuseki did not become ready on {url} within {timeout_s}s")


def _sparql_query(endpoint: str, q: str) -> int:
    """Run a SPARQL query; return the row count (parses JSON, forces full read)."""
    import json
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/sparql-results+json",
        },
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
    try:
        return len(json.loads(body).get("results", {}).get("bindings", []))
    except Exception:
        return -1


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    if not FUSEKI_JAR.exists():
        raise FileNotFoundError(
            f"Fuseki not installed at {FUSEKI_JAR}. "
            "Cache should have been populated during setup."
        )
    port = _pick_free_port()
    work = Path(tempfile.mkdtemp(prefix="fuseki-bench-"))
    tdb2_dir = work / "tdb2"
    tdb2_dir.mkdir()

    server_proc: subprocess.Popen | None = None
    rss_sampler: _PeakSampler | None = None

    try:
        # ---- bulk load via tdb2.tdbloader (timed) ----
        loader_cmd = [
            "java",
            "-Xmx4g",
            "-cp", str(FUSEKI_JAR),
            "tdb2.tdbloader",
            "--loc", str(tdb2_dir),
            "--loader", "phased",
            str(data_path),
        ]

        def _load() -> int:
            r = subprocess.run(loader_cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"tdbloader failed:\nSTDERR:\n{r.stderr}\nSTDOUT:\n{r.stdout}")
            return r.returncode

        _, load_t = time_once(_load)

        # ---- start fuseki-server over the loaded TDB2 dir ----
        server_cmd = [
            str(FUSEKI_SCRIPT),
            "--tdb2",
            f"--loc={tdb2_dir}",
            f"--port={port}",
            f"/{DATASET}",
        ]
        server_proc = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work),
            preexec_fn=os.setsid,  # so we can SIGTERM the whole group
        )

        endpoint = f"http://127.0.0.1:{port}/{DATASET}/query"
        _wait_for_http(f"http://127.0.0.1:{port}/$/ping", timeout_s=60.0)

        # start RSS sampler on the JVM PID (with children, in case of forks)
        rss_sampler = _PeakSampler(server_proc.pid, interval_s=0.05, include_children=True)
        rss_sampler.start()

        # ---- per-query best-of-3 + p50/p95 ----
        query_results: dict[str, Any] = {}
        for qid, qtext in queries.items():
            last, t = time_best_of(
                lambda q=qtext: _sparql_query(endpoint, q), n=3, warmup=1, timeout_s=300.0,
            )
            d = t.to_dict()
            d["row_count"] = int(last) if last is not None else 0
            query_results[qid] = d

        rss = rss_sampler.stop()
        rss_sampler = None

        return {
            "framework": NAME,
            "scale": scale,
            "data": str(data_path),
            "load_s": load_t,
            "queries": query_results,
            "rss_peak_bytes": rss.peak_bytes,
            "rss_delta_bytes": rss.delta_bytes,
            "store_bytes_on_disk": sum(
                p.stat().st_size for p in tdb2_dir.rglob("*") if p.is_file()
            ),
            "fuseki_version": "5.2.0",
        }
    finally:
        if rss_sampler is not None:
            rss_sampler.stop()
        if server_proc is not None and server_proc.poll() is None:
            try:
                os.killpg(server_proc.pid, signal.SIGTERM)
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server_proc.pid, signal.SIGKILL)
        shutil.rmtree(work, ignore_errors=True)
