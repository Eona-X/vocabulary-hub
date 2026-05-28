"""QLever adapter (Docker, native run inside the container).

Flow: spin up a detached container with the data dir mounted; exec
`qlever index` to build the index (timed = load); exec `qlever start` to
launch the server; query via HTTP from the host; sample peak RSS via
`docker stats` on the container; cleanup with `qlever stop` and `docker rm`.

The bench treats QLever as a server-only framework — no Turtle/N-Triples
write, no second clean-run RSS pass (the container is long-lived).
"""
from __future__ import annotations

import json
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

NAME = "qlever"
IMAGE = "adfreiburg/qlever:latest"

QLEVERFILE_TEMPLATE = """\
[data]
NAME         = bench
DESCRIPTION  = trainmarks-extended bench at {scale}

[index]
INPUT_FILES     = data.nt
CAT_INPUT_FILES = cat ${{INPUT_FILES}}
SETTINGS_JSON   = {{ "num-triples-per-batch": 1000000 }}

[server]
PORT         = 8888
ACCESS_TOKEN = bench-token

[runtime]
SYSTEM = native
IMAGE  = {image}

[ui]
UI_PORT   = 8176
UI_CONFIG = default
"""


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http(url: str, timeout_s: float = 60.0) -> None:
    """A 4xx response counts as 'alive' — the server is responding, just not happy with our probe."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status < 500:
                    return
        except urllib.error.HTTPError:
            return  # server is up, just rejected the probe path
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    raise TimeoutError(f"QLever did not become ready on {url} within {timeout_s}s")


def _sparql_query(endpoint: str, q: str) -> int:
    """Return row count from the parsed SPARQL JSON result."""
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


def _docker_stats_sampler(container: str, stop_evt: threading.Event) -> dict[str, int]:
    """Background thread: poll `docker stats --no-stream` and track peak RSS bytes."""
    peak = {"bytes": 0}
    while not stop_evt.is_set():
        try:
            out = subprocess.check_output(
                ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
            # format: "123.4MiB / 7.5GiB" — take the left side
            left = out.split("/")[0].strip()
            # parse units
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
    return peak


def run(data_path: Path, queries: dict[str, str], scale: str) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="qlever-bench-"))
    # qlever needs a clean working dir with data.nt and a Qleverfile
    nt_in_work = work / "data.nt"
    shutil.copy(data_path, nt_in_work)
    (work / "Qleverfile").write_text(QLEVERFILE_TEMPLATE.format(scale=scale, image=IMAGE))

    container = f"qlever-bench-{uuid.uuid4().hex[:8]}"
    host_port = _pick_free_port()

    # Start a long-lived container so we can exec build + start + stop in sequence
    subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "--name", container,
            "-u", f"{subprocess.check_output(['id', '-u']).decode().strip()}:"
                  f"{subprocess.check_output(['id', '-g']).decode().strip()}",
            "-v", f"{work}:/data",
            "-w", "/data",
            "-p", f"{host_port}:8888",
            "--entrypoint", "sleep",
            IMAGE,
            "3600",
        ],
        check=True,
        capture_output=True,
    )

    stop_evt = threading.Event()
    peak = {"bytes": 0}
    sampler_t = threading.Thread(
        target=lambda: peak.update(_docker_stats_sampler(container, stop_evt)),
        daemon=True,
    )

    try:
        # ---- bulk-load = build the index ----
        def _index() -> int:
            r = subprocess.run(
                ["docker", "exec", container, "bash", "-lc", "qlever index"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise RuntimeError(f"qlever index failed:\nSTDERR:\n{r.stderr}\nSTDOUT:\n{r.stdout}")
            return r.returncode

        _, load_t = time_once(_index)

        # ---- start server ----
        r = subprocess.run(
            ["docker", "exec", container, "bash", "-lc", "qlever start"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"qlever start failed:\nSTDERR:\n{r.stderr}\nSTDOUT:\n{r.stdout}")

        # start RSS sampler now (covers query phase + idle)
        sampler_t.start()

        endpoint = f"http://127.0.0.1:{host_port}/"
        _wait_http(endpoint, timeout_s=60.0)

        # ---- queries ----
        query_results: dict[str, Any] = {}
        for qid, qtext in queries.items():
            try:
                last, t = time_best_of(
                    lambda q=qtext: _sparql_query(endpoint, q), n=3, warmup=1, timeout_s=300.0,
                )
                d = t.to_dict()
                d["row_count"] = int(last) if last is not None else 0
                query_results[qid] = d
            except urllib.error.HTTPError as e:
                # QLever returns 500 with a JSON body containing the engine exception.
                body = e.read().decode(errors="replace")[:400] if hasattr(e, "read") else ""
                query_results[qid] = {"error": f"HTTP {e.code}", "body": body}
            except Exception as e:
                query_results[qid] = {"error": type(e).__name__, "message": str(e)}

        stop_evt.set()
        sampler_t.join(timeout=2)

        # ---- index size on disk ----
        index_bytes = sum(p.stat().st_size for p in work.rglob("*") if p.is_file())

        return {
            "framework": NAME,
            "scale": scale,
            "data": str(data_path),
            "load_s": load_t,
            "queries": query_results,
            "rss_peak_bytes": peak["bytes"],
            "store_bytes_on_disk": index_bytes,
            "qlever_image": IMAGE,
        }
    finally:
        stop_evt.set()
        try:
            subprocess.run(
                ["docker", "exec", container, "bash", "-lc", "qlever stop || true"],
                capture_output=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            pass
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)
