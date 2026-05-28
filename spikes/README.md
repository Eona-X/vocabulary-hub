# ADR-004 Validation Spikes

Harness for the five validation steps that gate moving ADR-004
(Re-selecting L1–L3 Components — Oxigraph, Maplib, Chrontext) from
**Proposed** to **Accepted**.

See [`docs/adr/004-l1-l3-component-reselection.md`](../docs/adr/004-l1-l3-component-reselection.md)
§ "Validation plan" for the source-of-truth requirements.

| # | Spike | Output | Decision it gates |
|---|---|---|---|
| 1 | [Oxigraph coverage](01_oxigraph_coverage/) | feature-matrix table | L1/L2 swap |
| 2 | [Oxigraph benchmark](02_oxigraph_bench/) | RSS, p50/p95, load throughput | L1/L2 swap |
| 3 | [Maplib RML conformance](03_maplib_rml_conformance/) | test-suite pass-rate vs. Morph-KGC | L3 ETL swap |
| 4 | [Maplib benchmark](04_maplib_bench/) | wall time, peak RSS on a public mapping | L3 ETL swap |
| 5 | [Virtualization scope](05_virtualization_scope/) | open scope-decision doc | Chrontext vs. ONTOP |

A spike fails ⇒ the corresponding incumbent named in ADR-004 (Jena/Fuseki,
Morph-KGC, ONTOP) stays.

## Greenfield assumption

This repository contains **only ADRs and design docs**. There is:

- no running Vocabulary Hub deployment,
- no incumbent Jena/Fuseki / Morph-KGC / ONTOP install to measure against,
- no hub-owned dataset, mapping, or query mix,
- no product owner yet to answer the Spike 5 scope question.

Every spike therefore:

1. **Stands up both candidates fresh, side by side**, in the same harness.
   "Jena/Fuseki" in a result table means an instance the harness booted
   for the comparison — not a production system.
2. **Uses public reference inputs** (DCAT, SKOS, FOAF, OWL test
   ontologies; the RML test suite; GTFS-Madrid-Bench). The set of inputs
   is committed under each spike's `inputs/`, so re-runs are reproducible.
3. **Records `inputs.kind = "public-reference"`** in every manifest.
   When/if hub-specific inputs ever exist, re-running with
   `inputs.kind = "hub"` will produce the gating numbers; the
   public-reference runs in this repo establish the methodology and an
   indicative baseline.

The Spike 1 coverage gate is similarly re-derived from the **documented
hub feature requirements** (README §Features, ADR-001, ADR-002, IDS-RAM
§3.5.6), not from runtime feature usage that doesn't exist yet.

## Provenance is mandatory

**Every spike run commits its raw output to `0N_*/results/<run-id>/`.**
That directory contains:

- `manifest.json` — UTC timestamp, git SHA, hostname, OS, Python version,
  tool versions, CLI args, input fixture hashes, `inputs.kind`.
- the raw outputs the spike produced (CSV / JSON / logs / SPARQL
  responses / per-test verdicts).
- a derived `summary.md` that the ADR reviewer reads.

Inputs (vocabularies, queries, mapping files, test-suite snapshots) are
committed under `0N_*/inputs/` so every result can be re-derived.
**Deterministically regenerated** fixtures (e.g. the 100k-triple bulk
SKOS dataset) are *not* committed — their generator script is, and the
input file hash in each manifest pins the version that produced the
run. Fetched external corpora (rml-test-cases, GTFS-Madrid-Bench) are
pinned by upstream commit SHA recorded next to the run script.

The shared helper `_lib/provenance.py` produces a stable `<run-id>`
(`YYYYMMDDTHHMMSSZ-<short-sha>-<inputs-hash>`) and writes the manifest;
every entry-point script calls it.

## Layout

```
spikes/
├── pyproject.toml         # uv-managed Python harness
├── docker/                # Fuseki + oxigraph-server compose stack
├── _lib/                  # shared helpers (provenance, RSS sampler, timing)
└── 0N_*/
    ├── README.md          # what this spike answers, how to run
    ├── run.sh             # entry point — writes results/<run-id>/
    ├── inputs/            # committed fixtures / vocabularies / queries
    ├── results/           # committed raw outputs, manifest, summary
    └── *.py               # spike code
```

## Setup

```bash
cd spikes
uv sync
docker compose -f docker/docker-compose.yml up -d   # spikes 1 & 2 only
```

Spikes run **independently** in any order. Re-running a spike creates a
new `results/<run-id>/` directory; previous runs are preserved.
