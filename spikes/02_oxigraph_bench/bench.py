"""Bulk-load + query-mix benchmark, side-by-side Fuseki vs Oxigraph.

Captures every response body so coverage drift is detectable later, plus
per-engine RSS time series sampled from the container's main process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.provenance import finish_run, start_run
from _lib.rss import RssSampler
from _lib.timing import LatencyTrace

SPIKE = "02_oxigraph_bench"
SPIKE_DIR = Path(__file__).resolve().parent
INPUTS = SPIKE_DIR / "inputs"
QUERIES_DIR = SPIKE_DIR / "queries"

# Bulk dataset is shared with Spike 1.
SHARED_BULK = Path(__file__).resolve().parents[1] / "01_oxigraph_coverage" / "inputs" / "bulk-100k.nt"
LOCAL_BULK = INPUTS / "bulk-skos.nt"

ENGINES = {
    "fuseki": {
        "container": "adr004-fuseki",
        "query": "http://localhost:3030/ds/query",
        "update": "http://localhost:3030/ds/update",
        "data_load": "http://localhost:3030/ds/data",
        "auth": ("admin", "admin"),
    },
    "oxigraph": {
        "container": "adr004-oxigraph",
        "query": "http://localhost:7878/query",
        "update": "http://localhost:7878/update",
        "data_load": "http://localhost:7878/store?default",
        "auth": None,
    },
}

WARMUP = 3
TIMED = 50


@dataclass
class LoadResult:
    engine: str
    triples: int
    seconds: float
    throughput_tps: float


def container_pid(container: str) -> int:
    out = subprocess.check_output(
        ["docker", "inspect", "-f", "{{.State.Pid}}", container],
        text=True,
    ).strip()
    return int(out)


def reset_dataset(engine: str) -> None:
    """DELETE WHERE clears the default graph; works on both engines."""
    ep = ENGINES[engine]
    requests.post(ep["update"], data={"update": "DELETE WHERE { ?s ?p ?o }"},
                  auth=ep.get("auth")).raise_for_status()


def bulk_load(engine: str, data: bytes, n_triples: int) -> LoadResult:
    ep = ENGINES[engine]
    t0 = time.time()
    r = requests.post(
        ep["data_load"], data=data,
        headers={"Content-Type": "application/n-triples"},
        timeout=600, auth=ep.get("auth"),
    )
    r.raise_for_status()
    dt = time.time() - t0
    return LoadResult(engine, n_triples, dt, n_triples / dt if dt > 0 else 0.0)


def run_query_mix(engine: str, raw_dir: Path) -> dict:
    """Returns {query_name: LatencyTrace.summary()}."""
    ep = ENGINES[engine]
    auth = ep.get("auth")
    out: dict[str, dict] = {}
    queries = sorted(QUERIES_DIR.glob("q*.rq")) + sorted(QUERIES_DIR.glob("q*.ru"))
    for q in queries:
        is_update = q.suffix == ".ru"
        url = ep["update" if is_update else "query"]
        body = q.read_text()
        param = "update" if is_update else "query"
        trace = LatencyTrace(label=q.stem)
        for _ in range(WARMUP):
            requests.post(url, data={param: body}, timeout=60, auth=auth)
        q_raw = raw_dir / q.stem
        q_raw.mkdir(parents=True, exist_ok=True)
        for i in range(TIMED):
            t0 = time.time()
            r = requests.post(url, data={param: body}, timeout=60, auth=auth)
            trace.add((time.time() - t0) * 1000)
            if i < 3:  # keep only the first three bodies — full set is wasteful
                (q_raw / f"{engine}.iter{i}.txt").write_text(
                    f"{r.status_code}\n{r.text[:8000]}"
                )
        out[q.stem] = trace.summary()
    return out


def main() -> int:
    if not LOCAL_BULK.exists():
        if SHARED_BULK.exists():
            LOCAL_BULK.symlink_to(SHARED_BULK)
        else:
            print(f"missing bulk dataset; run spike 1 first or "
                  f"`python ../01_oxigraph_coverage/inputs/gen_bulk.py 100000 > {LOCAL_BULK}`",
                  file=sys.stderr)
            return 2

    variant = os.environ.get("VARIANT", "tmpfs")
    if variant not in {"tmpfs", "disk"}:
        print(f"VARIANT must be 'tmpfs' or 'disk', got {variant!r}", file=sys.stderr)
        return 2

    data = LOCAL_BULK.read_bytes()
    n_triples = data.count(b" .\n")

    run_dir, manifest = start_run(
        spike=SPIKE, spike_dir=SPIKE_DIR,
        inputs=[LOCAL_BULK, *QUERIES_DIR.glob("q*")],
        tools=["pyoxigraph", "requests", "psutil"],
        args={"warmup": WARMUP, "timed": TIMED, "triples": n_triples, "variant": variant},
        notes=("Public-reference inputs (synthetic SKOS taxonomy + 8 hub-shaped queries). "
               f"Variant: {variant} — "
               + ("Fuseki --mem + Oxigraph tmpfs (engine-only)"
                  if variant == "tmpfs"
                  else "Fuseki TDB2 on volume + Oxigraph RocksDB on volume (deployment-realistic)")),
    )

    loads: list[LoadResult] = []
    latencies: dict[str, dict] = {}
    peak_rss: dict[str, float] = {}

    for engine in ENGINES:
        reset_dataset(engine)
        try:
            pid = container_pid(ENGINES[engine]["container"])
        except subprocess.CalledProcessError:
            print(f"container {ENGINES[engine]['container']} not running", file=sys.stderr)
            return 2
        with RssSampler(pid, engine, interval_s=0.25) as sampler:
            loads.append(bulk_load(engine, data, n_triples))
            latencies[engine] = run_query_mix(engine, run_dir / "raw")
        sampler.trace.write_csv(run_dir / f"rss_{engine}.csv")
        peak_rss[engine] = sampler.trace.peak_mb

    (run_dir / "load_results.json").write_text(json.dumps(
        [load.__dict__ for load in loads], indent=2))
    (run_dir / "query_latency.json").write_text(json.dumps(latencies, indent=2))

    write_summary(run_dir, loads, latencies, peak_rss, variant)
    finish_run(run_dir, manifest, {"peak_rss_mb": peak_rss, "variant": variant})
    print(f"results: {run_dir}")
    return 0


def write_summary(run_dir: Path, loads, latencies, peak_rss, variant: str) -> None:
    lines = [f"# Spike 2 summary — {run_dir.name}", "",
             f"Variant: **{variant}** "
             + ("(engine-only: Fuseki --mem, Oxigraph on tmpfs)"
                if variant == "tmpfs"
                else "(deployment-realistic: Fuseki TDB2 on volume, Oxigraph RocksDB on volume)"),
             "", "## Bulk load", "",
             "| engine | triples | seconds | throughput (t/s) |",
             "|---|---:|---:|---:|"]
    for l in loads:
        lines.append(f"| {l.engine} | {l.triples} | {l.seconds:.2f} | {l.throughput_tps:.0f} |")
    lines += ["", "## Peak RSS (container PID + children)", "",
              "| engine | peak RSS (MB) |", "|---|---:|"]
    for e, mb in peak_rss.items():
        lines.append(f"| {e} | {mb:.1f} |")
    lines += ["", "## Query latency (ms)", "",
              "| query | engine | p50 | p95 | p99 | mean |",
              "|---|---|---:|---:|---:|---:|"]
    for engine, by_q in latencies.items():
        for q, s in by_q.items():
            lines.append(f"| {q} | {engine} | {s['p50_ms']:.1f} | {s['p95_ms']:.1f} | "
                         f"{s['p99_ms']:.1f} | {s['mean_ms']:.1f} |")
    lines += ["",
              "**Note:** numbers are indicative until the hub team supplies a real",
              "dataset and query mix; the manifest records `inputs.kind = public-reference`."]
    (run_dir / "summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
