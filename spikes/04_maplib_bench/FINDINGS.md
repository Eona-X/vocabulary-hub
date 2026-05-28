# Spike 4 — findings

## TL;DR

The harness materialised the same mapping with Morph-KGC and Maplib at
scale 1. Morph-KGC produced 10 triples in 1.79 s at 254.9 MB peak RSS;
Maplib failed at template parse time with `expected IRI` and emitted 0
triples. There is no like-for-like comparison: ADR-004 §2's
"47×–182× faster than Morph-KGC on GTFS-Madrid-Bench" claim cannot be
reproduced on this host because Maplib's template language is stOTTR,
not RML, and rejects the mapping before any work is timed.

## Run identity

- Run id: `20260522T083109Z-98dac21-32d201`
- Scale: `1`
- Input kind: **synthetic fallback** (`inputs/synthetic/`)
- Results dir:
  `/home/nico/wspace/eona/eona_vocabulary_services/spikes/04_maplib_bench/results/20260522T083109Z-98dac21-32d201/`

GTFS-1 was not used: the upstream `oeg-upm/gtfs-bench` data generator
(`vig-1.8.1.jar`) requires a live MySQL source. The documented path is
the `oegdataintegration/gtfs-bench` Docker image, which is interactive
(prompts for scales and distributions and writes a `result.zip`) and
not runnable headless on this host. The synthetic fallback exercises
the same engine codepaths and is sufficient for the parse-time
verdict.

## Per-engine results

| engine | ok | wall (s) | peak RSS (MB) | triples | sha256(8) |
|---|---|---:|---:|---:|---|
| morph  | True  | 1.79 | 254.9 | 10 | `9c16d5ef` |
| maplib | False | 0.14 |   0.0 |  0 | `` |

Maplib's exact error from `bench_results.json`:

> `Template parsing error: error at 6:14: expected IRI parsing failed`

Output graphs match (canonical hash): **False**. Speedup not computed.

## What this means for the "47×–182×" claim

The figure cannot be reproduced here: Maplib never enters the timed
section because RML is not its input language. The published number is
also (a) single-benchmark — GTFS-Madrid-Bench only, (b) single-vendor
— DataTreehouse's own publication, and (c) tied to an earlier Maplib
API surface and template-language scope than the 0.20.x release this
spike pinned. Nothing in this spike either confirms or refutes the
number; it only shows the comparison cannot be set up as stated, on
this engine version, against an RML mapping.

## Why this is a coverage-gate failure under ADR-000 ranking

ADR-000 ranks drivers as **coverage → maturity → memory → performance**.
A candidate that fails coverage is rejected regardless of its
performance numbers. Maplib's mapping ingestion is stOTTR, an OTTR
dialect that is not RML/R2RML. The hub's mappings (and the
GTFS-Madrid-Bench reference) are RML. Spike 3
(`spikes/03_maplib_rml_conformance/`) documents this at suite scope:
Maplib does not run the `kg-construct/rml-test-cases` suite at all,
for the same root cause this spike hits on a single mapping. The
performance question is moot until coverage parity exists.

## What would have to change for Maplib to re-enter consideration

Either (a) Maplib ships an RML→OTTR transpiler that round-trips the
hub's mappings without semantic loss (joins, language tags, graph
maps, XML/JSON logical sources, function maps), or (b) the hub
commits to re-authoring every mapping as stOTTR and accepts owning
that dialect end-to-end. Both are non-trivial: (a) is a feature on
Maplib's roadmap that doesn't exist today; (b) is a hub-side rewrite
plus a permanent translation step against any RML-native tooling the
hub later integrates with. Neither is justified by a single-vendor
benchmark on one domain.

## What to keep from spike 4 for the next round

The harness is engine-agnostic. The RSS sampler (`_lib.rss.RssSampler`,
4 Hz on the process tree), the canonicalised count+hash diff, the
synthetic fallback, and the manifest/run-id machinery are all
independent of which engine is being benchmarked. Adding a future
RML-capable Rust engine is a single `bench_<engine>` function in
`bench.py` alongside `bench_morph` and `bench_maplib`; everything
downstream (`bench_results.json`, `summary.md`, RSS CSVs, raw outputs)
already handles N engines per scale. Re-using this for the next L3
candidate costs less than a day.
