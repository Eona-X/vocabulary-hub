"""Mapping-materialisation benchmark — Maplib vs Morph-KGC.

For every (engine, scale) the harness:
  1. starts an in-process RSS sampler against the *current* process tree
     for Maplib (in-process Python binding) or against the subprocess
     for Morph-KGC,
  2. invokes the engine to materialise the mapping,
  3. records wall time + peak RSS + output size + canonical hash.

The canonical-hash comparison means a "faster" engine that produces a
different graph is flagged, not celebrated.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.provenance import finish_run, start_run
from _lib.rss import RssSampler

SPIKE = "04_maplib_bench"
SPIKE_DIR = Path(__file__).resolve().parent
INPUTS = SPIKE_DIR / "inputs"


@dataclass
class BenchResult:
    engine: str
    scale: str
    wall_time_s: float
    peak_rss_mb: float
    output_triples: int
    output_hash: str
    ok: bool
    detail: str


def pick_mapping(scale: str) -> tuple[Path, Path]:
    """Return (mapping_path, working_dir).

    Prefer GTFS-Madrid-Bench at the chosen scale, fall back to the
    synthetic mini-mapping.
    """
    gtfs = INPUTS / "gtfs-madrid-bench" / f"scale-{scale}"
    if (gtfs / "mapping.ttl").exists():
        return gtfs / "mapping.ttl", gtfs
    syn = INPUTS / "synthetic"
    return syn / "mapping.ttl", syn


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def canonical_count_and_hash(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, ""
    try:
        import rdflib
        g = rdflib.Graph()
        g.parse(str(path))
        nt = sorted(g.serialize(format="nt").splitlines())
        return len(nt), sha256_text("\n".join(nt))
    except Exception:
        # fall back to naive count
        text = path.read_text(errors="replace")
        return text.count(" .\n"), sha256_text(text)


def bench_morph(mapping: Path, wd: Path, out: Path, scale: str, run_dir: Path) -> BenchResult:
    cfg = (
        f"[CONFIGURATION]\noutput_file={out}\n"
        f"[Dataset1]\nmappings={mapping}\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
        f.write(cfg)
        cfg_path = f.name
    t0 = time.time()
    try:
        proc = subprocess.Popen(
            ["uv", "run", "--isolated", "--with", "morph-kgc==2.10.0",
             "python", "-m", "morph_kgc", cfg_path],
            cwd=wd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        with RssSampler(proc.pid, "morph", interval_s=0.25) as s:
            out_b, err_b = proc.communicate(timeout=3600)
        ok = proc.returncode == 0
        dt = time.time() - t0
        s.trace.write_csv(run_dir / f"rss_morph_{scale}.csv")
        peak = s.trace.peak_mb
        triples, h = canonical_count_and_hash(out)
        detail = (out_b.decode(errors="replace") + err_b.decode(errors="replace"))[:1000]
        return BenchResult("morph", scale, dt, peak, triples, h, ok, detail)
    except Exception as e:
        return BenchResult("morph", scale, time.time() - t0, 0.0, 0, "", False,
                           f"{e}\n{traceback.format_exc()}")


def bench_maplib(mapping: Path, wd: Path, out: Path, scale: str, run_dir: Path) -> BenchResult:
    """Maplib 0.20.x renamed `Mapping` → `Model`, and its only template
    ingestion path is stOTTR (read_template), not RML. So pointing it at
    a GTFS-Madrid-Bench RML mapping fails at parse time. That failure IS
    the spike's finding for ADR-004 §2: there is no like-for-like speed
    comparison to make with Morph-KGC because Maplib cannot ingest RML."""
    t0 = time.time()
    try:
        # Maplib is in-process; sample the current PID + descendants.
        with RssSampler(os.getpid(), "maplib", interval_s=0.25) as s:
            from maplib import Model  # type: ignore
            m = Model()
            old_cwd = os.getcwd()
            try:
                os.chdir(wd)
                m.read_template(str(mapping))
                m.write(str(out), format="ntriples")
            finally:
                os.chdir(old_cwd)
        dt = time.time() - t0
        s.trace.write_csv(run_dir / f"rss_maplib_{scale}.csv")
        peak = s.trace.peak_mb
        triples, h = canonical_count_and_hash(out)
        return BenchResult("maplib", scale, dt, peak, triples, h, True, "")
    except Exception as e:
        return BenchResult("maplib", scale, time.time() - t0, 0.0, 0, "", False,
                           f"{e}\n{traceback.format_exc()}")


def main() -> int:
    scale = os.environ.get("SCALE", "1")
    mapping, wd = pick_mapping(scale)
    if not mapping.exists():
        print(f"no mapping found at {mapping}", file=sys.stderr)
        return 2

    is_synthetic = "synthetic" in str(wd)
    run_dir, manifest = start_run(
        spike=SPIKE, spike_dir=SPIKE_DIR,
        inputs=[mapping, *wd.glob("*.csv"), *wd.glob("*.json")],
        tools=["maplib", "morph-kgc", "rdflib", "psutil"],
        args={"scale": scale, "mapping": str(mapping)},
        inputs_kind="synthetic-fallback" if is_synthetic else "public-reference",
        notes="GTFS-Madrid-Bench at requested scale; synthetic fallback if absent.",
    )

    raw_dir = run_dir / "raw" / scale
    raw_dir.mkdir(parents=True, exist_ok=True)

    results = [
        bench_morph(mapping, wd, raw_dir / "morph.nt", scale, run_dir),
        bench_maplib(mapping, wd, raw_dir / "maplib.nt", scale, run_dir),
    ]

    (run_dir / "bench_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2)
    )
    write_summary(run_dir, results, scale)
    finish_run(run_dir, manifest, {"scale": scale,
                                   "output_hashes": {r.engine: r.output_hash for r in results}})
    print(f"results: {run_dir}")
    return 0


def write_summary(run_dir: Path, results: list[BenchResult], scale: str) -> None:
    by_engine = {r.engine: r for r in results}
    morph = by_engine.get("morph")
    maplib = by_engine.get("maplib")
    speedup = "n-a"
    if morph and maplib and maplib.wall_time_s > 0 and morph.ok and maplib.ok:
        speedup = f"{morph.wall_time_s / maplib.wall_time_s:.2f}×"
    same_hash = morph and maplib and morph.output_hash and morph.output_hash == maplib.output_hash

    lines = [
        f"# Spike 4 summary — {run_dir.name}",
        "", f"Scale: `{scale}`", "",
        "| engine | ok | wall time (s) | peak RSS (MB) | triples | sha256 (8) |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.engine} | {r.ok} | {r.wall_time_s:.2f} | {r.peak_rss_mb:.1f} | "
            f"{r.output_triples} | `{r.output_hash[:8]}` |"
        )
    lines += ["",
              f"Speedup (Morph/Maplib): **{speedup}**",
              f"Output graphs match (canonical hash): **{bool(same_hash)}**",
              "",
              "If `match = False`, the speedup is **not** a like-for-like comparison; "
              "investigate coverage divergence before quoting the number."]
    (run_dir / "summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
