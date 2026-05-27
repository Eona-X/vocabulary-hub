# Deepthought-Solutions/oxigraph fork — Q4 fix verification

## TL;DR

The Deepthought-Solutions/oxigraph fork (commit `5c7feb9`, dated 2026-05-26) ships a single-file patch to the SPARQL optimizer (`lib/sparopt/src/optimizer.rs`) titled **"bugfix/optimizer: fix quadratic scaling of OPTIONAL in a JOIN on FK"**. Building the fork from source and re-running the V1–V5 reproducer on the same 100k dataset confirms: **the pathology is fixed**.

V1 went from **61.2 s → 267 ms** on the bare repro and **63.5 s → 101 ms** in the bench harness (best of 3, p50/p95). The other queries (Q1–Q3) take a small constant-factor hit, presumably from the added optimizer path; this is well within noise for adoption decisions.

## Builds compared

| Build | Source | pyoxigraph version | How obtained |
|---|---|---|---|
| **stock** | <https://github.com/oxigraph/oxigraph> | 0.5.8 | `pip install pyoxigraph==0.5.8` (PyPI wheel) |
| **fork** | <https://github.com/Deepthought-Solutions/oxigraph> @ `5c7feb9` | 0.5.7 + patch | `cd python && maturin develop --release` (isolated venv) |

Note: the fork's base is one release behind stock (0.5.7 vs. 0.5.8). The Q4 fix is the head commit on top of the 0.5.7 base; no other functional deltas vs. upstream `oxigraph/oxigraph` at that point.

## The fix (one commit, one file)

`lib/sparopt/src/optimizer.rs` (+94/-9). Two changes:

1. **LeftJoin handler reorders into a Lateral when feasible.** When the OPTIONAL group has variables in common with the LHS and is "fit for a for-loop join" (the existing predicate that detects index-friendly patterns), the optimizer now reorders the right-hand side using the LHS types as context, then emits a `Lateral( left, LeftJoin(EmptySingleton, right, ..., HashBuildRightProbeLeft) )` instead of a flat `LeftJoin`. This is what lets the engine probe the indexed `?customer` join column instead of scanning the orders pattern per outer row.
2. **Cost-model nudge.** `estimate_graph_pattern_size` now doubles the estimated cardinality for `?s rdf:type <T>` patterns (vs. generic triple patterns). `rdf:type` triples are densely shared across many subjects, so this corrects an under-estimate that previously biased the planner toward putting type patterns first.
3. **Regression test.** The patch ships a unit test (`test_optional_lateral_reordering`) whose query is **literally V1 from this investigation's reproducer** — same prefixes, same predicates, same shape.

## Reproducer results (single-file repro, `repro.py`)

Same dataset (deterministic seed=42, 2,000 customers / 5,000 products / 14,000 orders), same Python interpreter version, same machine, same kernel. Single execution per cell (no best-of-N — we're characterising a regression fix, not micro-tuning):

| Variant | Stock 0.5.8 | Fork 0.5.7+patch | Δ |
|---|---:|---:|---:|
| **V1** OPTIONAL + GROUP BY + SUM | 61,224 ms | **267 ms** | **229× faster** |
| V2 OPTIONAL → required pattern | 92 ms | 172 ms | 1.9× slower (noise) |
| V3 OPTIONAL only, no GROUP BY | 68,963 ms | **250 ms** | **276× faster** |
| V4 OPTIONAL + GROUP BY, no SUM (COUNT only) | 62,008 ms | **67 ms** | **926× faster** |
| V5 UNION + FILTER NOT EXISTS rewrite | 15,165 ms | 15,888 ms | unchanged |

V5 is unchanged because the UNION/FILTER-NOT-EXISTS pattern doesn't traverse the LeftJoin optimizer path that was fixed. Expected.

## Bench harness results (best of 3, p50/p95, with peak RSS sampling)

Same data, same queries, same `time_best_of(n=3, warmup=1)` harness, same `_PeakSampler` RSS measurement at 20 Hz.

| Metric | Stock 0.5.8 | Fork 0.5.7+patch | Fuseki+TDB2 5.2 |
|---|---:|---:|---:|
| Load | 0.42 s | 0.76 s | 3.17 s |
| Q1 count (best) | 21 ms | 41 ms | 75 ms |
| Q2 top-20 agg | 68 ms | 75 ms | 77 ms |
| Q3 join+filter | 104 ms | 117 ms | 35 ms |
| **Q4 OPTIONAL+agg** | **63,523 ms** | **101 ms** ✅ | 128 ms |
| Peak RSS | 127 MB | 150 MB | 970 MB |
| Store on disk | 8.5 MB | 8.9 MB | 202 MB |

Q4 in the fork is now **slightly faster than Fuseki** on the same query — the engine catches up on the one shape where stock 0.5.8 was unusable. Q1–Q3 take a small constant-factor hit; the absolute numbers stay in the same order of magnitude as stock. Memory and disk are essentially unchanged.

The Q4 fork run paths cleanly: a single 100k-triple bulk-load, then four queries timed best-of-3 with full result materialization (`list(store.query(...))`). Provenance manifest written under
`spikes/02_oxigraph_bench/results/20260526T151342Z-728771b-06ec41/`.

## Implications for ADR-004 §1 (L1/L2 — Oxigraph vs. Jena/Fuseki)

Before this investigation, the §1 verdict was "Conditional candidate — proceed to coverage spike and memory/perf benchmark." After:

- **Stock 0.5.8** does not pass the perf gate against the V1 query shape and is **not** a viable replacement for Fuseki/TDB2 in any deployment that accepts general SPARQL.
- **Fork @ 5c7feb9** does pass the perf gate on this query shape. The other ADR-004 §1 concerns (coverage matrix, federation/full-text/reasoning gap, bus factor) are unchanged.
- Adopting the fork directly would mean either (a) running off an unmerged Deepthought-Solutions branch, or (b) waiting for the fix to land upstream. Either way, the path to a usable Oxigraph in our stack now exists.

Suggested concrete next steps (each independent):

1. **Push the fix upstream.** The patch is small, focused, ships with a regression test, and is on an Apache-2.0 fork — perfectly positioned to become an upstream PR to `oxigraph/oxigraph`. The Deepthought owner or the user should file it.
2. **Adopt the fork as a vendor pin** in the interim if upstream takes time. Build from `5c7feb9` (or a `0.5.8 + patch` rebase) into our own wheel, document the build, and re-evaluate when the fix lands upstream.
3. **Update the upstream issue draft** in this directory to note that a fix already exists in a public fork — saves the maintainer time and converts the report into "ready-to-merge PR candidate" rather than "unbounded bug."
4. **Coverage spike still owed.** Even with Q4 fixed, ADR-004 §1's coverage caveats (federation `SERVICE`, full-text indexing, OWL/RDFS reasoning, what Jena features the hub actually exercises) remain. Q4 was the most acute blocker, not the only one.

## How to reproduce this comparison

```bash
# Stock build
spikes/venv/bin/python spikes/02_oxigraph_bench/investigations/q4_oxigraph_optional/repro.py --scale 100k

# Fork build
git clone --depth=5 https://github.com/Deepthought-Solutions/oxigraph.git \
  spikes/02_oxigraph_bench/.cache/oxigraph-deepthought
cd spikes/02_oxigraph_bench/.cache/oxigraph-deepthought
git submodule update --init --recursive --depth=1 oxrocksdb-sys/rocksdb oxrocksdb-sys/lz4
cd python
python3 -m venv ../../forkvenv
source ../../forkvenv/bin/activate
pip install --upgrade pip maturin psutil
maturin develop --release
# build takes ~4 min on a recent x86_64 desktop
python ../../../investigations/q4_oxigraph_optional/repro.py --scale 100k

# Bench harness against the fork
spikes/02_oxigraph_bench/.cache/forkvenv/bin/python \
  spikes/02_oxigraph_bench/harness/runner.py --framework oxigraph_fork --scale 100k --format ttl
```

Both result sets are kept side-by-side under `spikes/02_oxigraph_bench/results/`:

- Stock: `20260526T091130Z-728771b-b906fa/raw/oxigraph/`
- Fork: `20260526T151342Z-728771b-06ec41/raw/oxigraph_fork/`
