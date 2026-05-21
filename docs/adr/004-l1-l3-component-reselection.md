# ADR-004: Re-selecting L1–L3 Components — Oxigraph, Maplib, Chrontext

- **Status**: Proposed
- **Date**: 2026-05-21
- **Layer / Purpose**: L1 Storage, L2 Services, L3 Mapping — *component re-selection*
- **Context**: Re-evaluating component choices at L1–L3 against the ADR-000 driver ranking, prompted by maturity progress in the Oxigraph / Polars-Arrow ecosystems since ADR-001 and ADR-002 were written.
- **Related**: [ADR-000](000-adr-process-and-constraints.md) (Drivers), [ADR-001](001-triplestore-stack-selection.md) (amends), [ADR-002](002-mapping-and-virtualization.md) (amends). L5 IDS conformance is **out of scope** and handled separately in a future ADR.

## Context

ADR-001 selected Apache Jena/Fuseki for L1/L2 and ADR-002 selected ONTOP + Morph-KGC for L3, both decided largely on the **maturity** axis given the immaturity of alternatives at the time. Two ecosystem shifts justify revisiting those choices:

1. Oxigraph has cut tagged releases with SPARQL 1.1 query/update coverage and a RocksDB-backed persistent store.
2. The Polars/Arrow toolchain has produced semantic-layer engines (Maplib, Chrontext) with published benchmarks against the incumbents.

This ADR evaluates whether those components now clear the **coverage + maturity gate** set in ADR-000, and if so, how they compare on **memory and performance** — the only drivers that should decide between qualifying candidates. Per ADR-000, runtime language is not itself a driver; it is mentioned only where in-process embedding actually changes the operational picture.

Scope: L1 (triplestore), L2 (SPARQL service), L3 (mapping / virtualization). **L5 (IDS adapter) is explicitly excluded** — Rust IDS tooling does not clear the IDSA conformance gate today and is decided in a separate ADR.

## Candidates under evaluation

| Layer | Incumbent (prior ADR) | Candidate | Section |
|---|---|---|---|
| L1 Storage | Apache Jena TDB2 (ADR-001) | Oxigraph (RocksDB backend) | §1 |
| L2 SPARQL service | Fuseki (ADR-001) | `oxigraph-server` | §1 |
| L3 ETL mapping | Morph-KGC (ADR-002) | Maplib | §2 |
| L3 Virtualization | ONTOP (ADR-002) | Chrontext | §3 |

Each candidate is evaluated against the ADR-000 ranking: **(1) coverage → (2) maturity → (3) memory → (4) performance**. A candidate that fails (1) or (2) is rejected regardless of how it scores on (3) and (4).

---

## §1. L1/L2 — Oxigraph vs. Jena/Fuseki

### Coverage
- SPARQL 1.1 Query and Update: supported. Confirm conformance against the W3C test suite before adoption.
- RDF 1.1 (named graphs, datasets): supported.
- Federation (`SERVICE`), full-text indexing, reasoning: **gaps to verify.** Jena ships ARQ federation, Lucene/Elastic text indexes, and OWL/RDFS reasoners out of the box. If the hub depends on any of these in production query paths, this is a coverage failure.
- Bulk load formats (N-Quads, TriG, RDF/XML, JSON-LD): supported via `oxttl`/`oxrdfio`.

**Action required before acceptance:** enumerate which Jena features are actually exercised in the current deployment and check each against Oxigraph's feature matrix. Without this list, the coverage gate is not passed.

### Maturity
- Tagged releases, semantic versioning, active maintenance (verify last-release cadence at acceptance time).
- Governance: maintained primarily by Tpt; smaller contributor base than Jena. Bus factor is a real risk and should be acknowledged.
- Production deployments: list known users before claiming "production maturity."

### Memory
- Order-of-magnitude lower RSS than Jena/Fuseki is plausible (no JVM heap, no metaspace) but the "10x" figure from prior drafts is not substantiated. **Required:** benchmark both on the hub's actual dataset size and query mix before deciding.

### Performance
- Bulk-load and point-query benchmarks exist in the Oxigraph repo; reproduce on representative data before deciding.

### Embedding note (not a driver, but operationally relevant)
ADR-001 made co-location with the IDS adapter a driver because Jena `Model` objects were passed in-process to the Java EDC. If L5 stays on EDC (per the scope exclusion above), Oxigraph would sit behind an HTTP boundary and the previous in-process argument no longer favors Jena — but it also doesn't favor Oxigraph. Neutral.

### Verdict
**Conditional candidate.** Proceed to a coverage spike (feature-matrix check) and a memory/perf benchmark on real data. Reject if any used Jena feature has no Oxigraph equivalent.

---

## §2. L3 ETL — Maplib vs. Morph-KGC

### Coverage
- RML / R2RML: supported via Maplib's mapping layer and the OTTR template system. **Required:** run the RML test suite and report pass rate vs. Morph-KGC's.
- CSVW: verify.
- Output formats and target stores: verify Arrow-to-RDF serialization paths match what the hub's downstream consumers expect.

### Maturity
- Single-vendor (DataTreehouse). Smaller contributor base than the RMLio ecosystem behind Morph-KGC.
- Release cadence and issue-response times to be reported at acceptance.
- MappingLoom-RS, referenced in earlier drafts, is dropped from this ADR until its status is verifiable.

### Memory
- Arrow columnar representation typically lower than row-oriented Python pipelines, but quantify on the hub's largest expected mapping job.

### Performance
- Published claim: "47x–182x faster than Morph-KGC" on GTFS-Madrid-Bench. **One benchmark, one domain, vendor-published.** Treat as a hint, not evidence. Required before acceptance: reproduce on the hub's own mapping workload.

### Verdict
**Conditional candidate.** Coverage spike (RML test suite) is the gating step; performance numbers come second.

---

## §3. L3 Virtualization — Chrontext vs. ONTOP

### Coverage
- ONTOP is a general OBDA engine over arbitrary SQL sources with full SPARQL-to-SQL rewriting and OWL 2 QL reasoning.
- Chrontext is **narrower by design**: a hybrid engine for SPARQL queries that join a knowledge graph with a time-series / analytical database.
- **This is a coverage mismatch, not a like-for-like replacement.** If the hub's virtualization needs are limited to time-series joins, Chrontext fits. If general SQL virtualization is required, Chrontext does not pass the gate.

### Maturity
- Single-vendor, narrow community. Same caveats as Maplib.

### Verdict
**Reject as a direct ONTOP replacement** unless the hub's virtualization scope is formally narrowed to time-series hybrid queries. If it is, Chrontext becomes a candidate and the coverage/maturity/memory/perf evaluation proceeds. Otherwise, keep ONTOP and re-open this when a general-purpose Rust OBDA engine appears.

---

## Decision

Conditional on the spikes listed below passing:

1. **L1/L2:** Replace Jena/Fuseki with Oxigraph, contingent on the coverage-matrix spike.
2. **L3 ETL:** Replace Morph-KGC with Maplib, contingent on RML test-suite pass-rate parity.
3. **L3 Virtualization:** **Keep ONTOP.** Chrontext is a different product, not a replacement.

If any spike fails, the corresponding incumbent stays.

## Consequences

- **Positive (if spikes pass):**
  - Lower memory footprint at L1/L2 (magnitude TBD by benchmark, not assumed).
  - Faster ETL materialization at L3 (magnitude TBD by benchmark).
  - Fewer runtime dependencies in the container image.
- **Negative:**
  - Smaller upstream communities than Jena / RMLio. Higher bus-factor risk.
  - In-house expertise required for the new components; document operational runbooks before cutover.
  - ADR-001 and ADR-002 are partially superseded; update their status lines on acceptance.

## Validation plan (must complete before status moves to Accepted)

1. **Oxigraph coverage spike:** enumerate Jena features in use; check each against Oxigraph. Output: feature-matrix table.
2. **Oxigraph benchmark:** bulk-load and query-mix benchmark on a representative dataset. Output: RSS, p50/p95 latency, load throughput vs. Jena/Fuseki.
3. **Maplib RML conformance:** run the RML test suite. Output: pass-rate vs. Morph-KGC.
4. **Maplib benchmark:** materialize the hub's largest mapping on both engines. Output: wall time, peak RSS.
5. **Scope decision on virtualization:** product owner confirms whether general SQL virtualization is in scope. If no, run Chrontext through the same gate; if yes, ONTOP stays and Chrontext is closed out.

## References

- [Oxigraph — GitHub](https://github.com/oxigraph/oxigraph)
- [Chrontext — GitHub](https://github.com/DataTreehouse/chrontext)
- [Maplib — GitHub](https://github.com/DataTreehouse/maplib)
- [W3C SPARQL 1.1 Test Suite](https://www.w3.org/2009/sparql/docs/tests/)
- [RML Test Cases](https://rml.io/test-cases/)
