# Spike 4 — Maplib vs Morph-KGC mapping benchmark

**Gates:** L3 ETL swap (ADR-004 §2).

## What this spike answers

ADR-004 requires "materialize the hub's largest mapping on both engines.
Output: wall time, peak RSS." The hub has no mappings yet. The harness
uses **GTFS-Madrid-Bench** — the exact benchmark cited in ADR-004 §2
("47×–182× faster than Morph-KGC on GTFS-Madrid-Bench") — so the spike
either reproduces or refutes the vendor's claim under our hardware.

GTFS-Madrid-Bench was chosen because:

- It is public, scaled (1×, 10×, 100×, 1000× variants), and well-known.
- ADR-004 cites it explicitly, so reproducing it here directly addresses
  the ADR's open question.
- Once a hub mapping exists, swapping it into `inputs/` and re-running
  yields a `inputs.kind = "hub"` gating run with no harness changes.

## Inputs

`inputs/`:

- `gtfs-madrid-bench/` — fetched by `run.sh` from the
  [SDM-TIB/GTFS-Madrid-Bench](https://github.com/oeg-upm/gtfs-bench)
  repository. Pinned commit recorded in `inputs/.bench_commit`.
- `scale.txt` — chosen scale factor (default `1`; override with
  `SCALE=10 ./run.sh`). Recorded in the manifest.

If neither materialises (e.g. offline), the harness falls back to a
minimal synthetic mapping in `inputs/synthetic/` and tags the manifest
accordingly.

> **Note on GTFS-1 data generation on this host.** The upstream
> `oeg-upm/gtfs-bench` generator (`vig-1.8.1.jar`) requires a live MySQL
> source — the documented path is `docker run … oegdataintegration/gtfs-bench`,
> which is interactive (asks for scales / distributions) and writes a
> `result.zip` to the cwd. Re-runs on a host with Docker should drop the
> resulting `csvs/1/` and `gtfs-csv.rml.ttl` into
> `inputs/gtfs-madrid-bench/scale-1/` to switch from the synthetic
> fallback to the real benchmark.

## Engine outcome (current ADR-004 finding)

On the synthetic mapping (and equally on any RML mapping including the
GTFS-Madrid-Bench one), Maplib 0.20.x's `read_template` rejects RML at
parse time — its template language is stOTTR, not RML. So the
"47×–182× faster than Morph-KGC" claim from ADR-004 §2 **cannot be
reproduced** here: there is no like-for-like comparison while Maplib
cannot ingest the same mapping Morph-KGC does. The recorded failure
mode (`Template parsing error: error at L:C: expected IRI`) is the
same finding spike 3 documents at suite scope.

## Metrics captured per (engine × scale)

- `wall_time_s` — total materialisation time, from process start to
  output file fsynced.
- `peak_rss_mb` — sampled at 4 Hz from `_lib.rss.RssSampler` on the
  engine's process tree.
- `output_triples` — line count of the canonicalised output.
- `output_hash` — sha256 of the canonicalised output; differing hashes
  across engines mean the speed comparison is moot until coverage is
  reconciled.

## Outputs

```
results/<run-id>/
├── manifest.json
├── bench_results.json       # one row per (engine, scale) with metrics above
├── rss_<engine>_<scale>.csv
├── raw/<scale>/<engine>.nt  # actual materialised output (for diffing)
└── summary.md
```

## Re-running

```bash
./run.sh                  # scale 1
SCALE=10 ./run.sh         # scale 10
SCALE=100 ./run.sh        # scale 100 — multi-GB output
```
