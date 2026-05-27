"""Bench orchestrator.

Opens a timestamped run dir, loads queries + data path, dispatches to a
framework adapter, writes result JSON.
"""
from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
SPIKE_DIR = HARNESS_DIR.parent
SPIKES_ROOT = SPIKE_DIR.parent          # so `_lib.*` imports resolve
REPO_ROOT = SPIKES_ROOT.parent

# put both on sys.path: spikes/ for shared _lib, harness/ for frameworks.*
for p in (SPIKES_ROOT, HARNESS_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from _lib.provenance import open_run, write_result  # noqa: E402

QUERIES_DIR = SPIKE_DIR / "queries"
DATA_DIR = SPIKE_DIR / "data"
RESULTS_DIR = SPIKE_DIR / "results"


def load_queries() -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted(QUERIES_DIR.glob("*.rq"))}


def resolve_data(scale: str, fmt: str) -> Path:
    p = DATA_DIR / f"data-{scale}.{fmt}"
    if not p.exists():
        raise FileNotFoundError(
            f"Missing dataset {p}. Run: python harness/generate_data.py --scale {scale}"
        )
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--framework", required=True,
                    help="module under harness/frameworks/ (e.g. 'oxigraph')")
    ap.add_argument("--scale", default="100k")
    ap.add_argument("--format", default="nt", choices=["nt", "ttl"])
    ap.add_argument("--skip-queries", default="",
                    help="comma-separated query IDs to skip (e.g. 'q4_optional_agg')")
    args = ap.parse_args()

    data = resolve_data(args.scale, args.format)
    queries = load_queries()
    skip = {s.strip() for s in args.skip_queries.split(",") if s.strip()}
    if skip:
        queries = {k: v for k, v in queries.items() if k not in skip}

    run_dir, manifest = open_run(
        spike="02_oxigraph_bench",
        results_root=RESULTS_DIR,
        inputs={"data": data, **{f"q_{k}": QUERIES_DIR / f"{k}.rq" for k in queries}},
        config={"framework": args.framework, "scale": args.scale, "format": args.format,
                "skipped_queries": sorted(skip)},
        repo_root=REPO_ROOT,
    )
    print(f"run_id={manifest.run_id}")

    mod = importlib.import_module(f"frameworks.{args.framework}")
    try:
        result = mod.run(data, queries, args.scale)
        out = write_result(run_dir, mod.NAME, result)
        print(f"wrote {out}")
    except Exception as e:
        write_result(run_dir, args.framework, {
            "framework": args.framework,
            "scale": args.scale,
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        raise


if __name__ == "__main__":
    main()
