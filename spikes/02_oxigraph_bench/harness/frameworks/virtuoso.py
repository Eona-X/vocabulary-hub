"""Virtuoso adapter (Docker, openlink/virtuoso-opensource-7:latest).

Flow: detached container with DirsAllowed=/database; bulk-load via isql
ld_dir + rdf_loader_run + checkpoint; query via HTTP /sparql with
default-graph-uri. RSS via docker stats.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from _lib.timing import time_best_of, time_once

NAME = "virtuoso"
IMAGE = "openlink/virtuoso-opensource-7:latest"
GRAPH_IRI = "http://bench/graph"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http(url: str, timeout_s: float = 120.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status < 500:
                    return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    raise TimeoutError(f"Virtuoso did not become ready on {url} within {timeout_s}s")


def _sparql_query(endpoint: str, q: str) -> int:
    """Return row count from the parsed SPARQL JSON result."""
    import json
    data = urllib.parse.urlencode({
        "query": q,
        "default-graph-uri": GRAPH_IRI,
    }).encode()
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


def _docker_rss_loop(container: str, stop_evt: threading.Event, peak: dict[str, int]) -> None:
    while not stop_evt.is_set():
        try:
            out = subprocess.check_output(
                ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
                text=True, stderr=subprocess.DEVNULL, timeout=5,
            ).strip()
            left = out.split("/")[0].strip()
            for suf, mul in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10), ("B", 1)):
                if left.endswith(suf):
                    try:
                        b = int(float(left[: -len(suf)]) * mul)
                        if b > peak["bytes"]:
                            peak["bytes"] = b
                    except ValueError:
                        pass
                    break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        stop_evt.wait(0.25)


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    if data_path.suffix != ".ttl":
        raise ValueError(f"Virtuoso adapter expects Turtle input, got {data_path}")

    work = Path(tempfile.mkdtemp(prefix="virtuoso-bench-"))
    (work / "data").mkdir()
    shutil.copy(data_path, work / "data" / "data.ttl")

    container = f"virtuoso-bench-{uuid.uuid4().hex[:8]}"
    sparql_port = _pick_free_port()
    isql_port = _pick_free_port()

    subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "--name", container,
            "-e", "DBA_PASSWORD=dba",
            "-e", "VIRT_Parameters_DirsAllowed=., /opt/virtuoso-opensource/share/virtuoso/vad, /database",
            "-v", f"{work}:/database",
            "-p", f"{sparql_port}:8890",
            "-p", f"{isql_port}:1111",
            IMAGE,
        ],
        check=True, capture_output=True,
    )

    stop_evt = threading.Event()
    peak = {"bytes": 0}
    sampler = threading.Thread(
        target=_docker_rss_loop, args=(container, stop_evt, peak), daemon=True,
    )

    try:
        sparql_endpoint = f"http://127.0.0.1:{sparql_port}/sparql"
        _wait_http(sparql_endpoint, timeout_s=120.0)
        sampler.start()

        # ---- bulk load (timed) ----
        load_sql = (
            f"ld_dir('/database/data', 'data.ttl', '{GRAPH_IRI}'); "
            f"rdf_loader_run(); "
            f"checkpoint;"
        )

        def _load() -> int:
            r = subprocess.run(
                ["docker", "exec", container, "isql", "1111", "dba", "dba", f"exec={load_sql}"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise RuntimeError(f"isql load failed:\n{r.stderr}\n{r.stdout}")
            return r.returncode

        _, load_t = time_once(_load)

        # ---- queries ----
        query_results: dict[str, Any] = {}
        for qid, qtext in queries.items():
            try:
                last, t = time_best_of(
                    lambda q=qtext: _sparql_query(sparql_endpoint, q), n=3, warmup=1,
                    timeout_s=300.0,
                )
                d = t.to_dict()
                d["row_count"] = int(last) if last is not None else 0
                query_results[qid] = d
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:400] if hasattr(e, "read") else ""
                query_results[qid] = {"error": f"HTTP {e.code}", "body": body}
            except Exception as e:
                query_results[qid] = {"error": type(e).__name__, "message": str(e)}

        stop_evt.set()
        sampler.join(timeout=2)

        # files in /database are owned by the container user; query from inside
        try:
            r = subprocess.run(
                ["docker", "exec", container, "du", "-sbL", "/database"],
                capture_output=True, text=True, timeout=10,
            )
            store_bytes = int(r.stdout.split()[0]) if r.returncode == 0 else 0
        except Exception:
            store_bytes = 0

        return {
            "framework": NAME,
            "scale": scale,
            "data": str(data_path),
            "load_s": load_t,
            "queries": query_results,
            "rss_peak_bytes": peak["bytes"],
            "store_bytes_on_disk": store_bytes,
            "virtuoso_image": IMAGE,
        }
    finally:
        stop_evt.set()
        # remove the DB files as the container user first; otherwise host can't unlink them
        subprocess.run(
            ["docker", "exec", container, "sh", "-c", "rm -rf /database/* /database/.??* 2>/dev/null"],
            capture_output=True, timeout=10,
        )
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)
