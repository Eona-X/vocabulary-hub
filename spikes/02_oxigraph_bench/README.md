# Spike 02 — L1/L2 Triplestore Bench (extended trainmarks)

Validates ADR-004 step 2 (Oxigraph bulk-load + query bench vs. the Jena/Fuseki incumbent) and extends scope to every L1/L2 candidate that clears the **ADR-000 OSI gate**.

## Scope vs. trainmarks

[DataTreehouse/trainmarks](https://github.com/DataTreehouse/trainmarks) is the methodological reference but is **re-implemented here**, not vendored — the upstream repo has no license file. We mirror its query mix (Q1 count, Q2 top-N aggregation, Q3 multi-join + filter, Q4 OPTIONAL + aggregation) and synthetic e-commerce schema so numbers are roughly comparable, but the harness and data generator are our own.

### Methodology deltas vs. trainmarks

| Aspect | trainmarks | This spike |
|---|---|---|
| Stats | best-of-3 only | best-of-3 **+ p50 + p95** (after a warmup) |
| Memory | not measured | **peak RSS** sampled at 20 Hz, includes child processes |
| Jena | in-memory `Model` only | **Fuseki + TDB2** (the actual ADR-001 incumbent) |
| RDF4J | `MemoryStore` SAIL only | **NativeStore / LMDB** disk backends |
| Provenance | none | `{ts}-{git-sha}-{input-hash}` run dirs + manifest.json |

### Framework matrix

| Framework | Layer | License | In trainmarks? | Status |
|---|---|---|---|---|
| Oxigraph (RocksDB), stock 0.5.8 | L1+L2 | MIT/Apache-2.0 | yes | **in** — ADR-004 candidate |
| Oxigraph (RocksDB), Deepthought fork @ 5c7feb9 | L1+L2 | MIT/Apache-2.0 | no | **in** — fixes the Q4 OPTIONAL pathology found in stock 0.5.8 ([fork_comparison.md](investigations/q4_oxigraph_optional/fork_comparison.md)) |
| Apache Jena Fuseki + TDB2 | L1+L2 | Apache-2.0 | no (only in-mem Model) | **in** — ADR-001 incumbent |
| Eclipse RDF4J Native/LMDB | L1+L2 | EDL-1.0 | no (only MemoryStore) | **in** — fills RDF4J disk gap |
| TerminusDB | L1+L2 | Apache-2.0 | no | **in** — git-like versioning aligns w/ hub model |
| HDT (hdt-java/hdt-cpp) | L1 (read-only) | LGPL | no | **in** — compact serve-only path for vocabularies |
| QLever | L2 | Apache-2.0 | yes | in (port from trainmarks) |
| Virtuoso (Docker) | L1+L2 | GPLv2 | yes | in (port from trainmarks) |
| Maplib (in-memory) | L1 | Apache-2.0 | yes | in (cross-reference w/ spike 04) |
| rdflib | L1 | BSD-3 | yes | in (Python baseline) |
| dotNetRDF | L1 | MIT | yes | in (port from trainmarks) |
| Neo4j + n10s | L1 (RDF-import) | GPLv3 | yes | **out** — property graph, not native RDF |
| Apache Jena in-memory `Model` | — | Apache-2.0 | yes | **out** — non-production form of Jena |
| **maplib (disk)** | L1 | **Proprietary** | yes | **out** — fails ADR-000 |
| **GraphDB Free** | L1+L2 | **Proprietary** | yes | **out** — fails ADR-000 |
| Apache Rya | L1 | Apache-2.0 | no | deferred (Accumulo dep is heavy) |

## Layout

```
02_oxigraph_bench/
├── README.md                  ← you are here
├── data/                      ← generated .ttl/.nt at multiple scales
├── queries/                   ← Q1-Q4 SPARQL files
├── harness/
│   ├── generate_data.py       ← deterministic synthetic generator
│   ├── runner.py              ← orchestrator: opens run dir, dispatches per-framework
│   └── frameworks/            ← one adapter per framework
│       ├── oxigraph.py
│       ├── fuseki_tdb2.py     (todo)
│       ├── rdf4j_native.py    (todo)
│       ├── terminusdb.py      (todo)
│       └── hdt.py             (todo)
├── inputs/                    ← (existing — kept for future input fixtures)
└── results/
    └── {UTC}-{sha}-{hash}/    ← one dir per run
        ├── manifest.json
        └── raw/{framework}/result.json
```

## Status

- [x] `_lib` helpers (provenance/rss/timing) rewritten
- [x] Scaffold + README
- [ ] Data generator + 4 queries
- [ ] Oxigraph adapter + smoke run
- [ ] Fuseki + TDB2 adapter (incumbent, highest-priority gap)
- [ ] RDF4J Native, TerminusDB, HDT adapters
- [ ] Port remaining trainmarks frameworks (rdflib, QLever, Virtuoso, dotNetRDF, maplib)
- [ ] Aggregation + report

## How to run (work-in-progress)

```bash
# from repo root, with venv activated
spikes/venv/bin/python spikes/02_oxigraph_bench/harness/generate_data.py --scale 100k
spikes/venv/bin/python spikes/02_oxigraph_bench/harness/runner.py --framework oxigraph --scale 100k
```
