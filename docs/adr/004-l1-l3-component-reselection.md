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
| L3 ETL mapping | Morph-KGC (ADR-002) | Maplib (**rejected — coverage**) | §2 |
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

### Coverage — **fails the gate** (see Spike 3 + Spike 4)

- **Maplib 0.20.18 does not ingest RML or R2RML.** Its only template
  ingestion path is `Model.read_template`, which parses **stOTTR** — a
  non-RML OTTR template dialect. Pointing it at any `mapping.ttl` from
  the kg-construct RML test cases or from GTFS-Madrid-Bench fails at
  parse time (`Template parsing error: error at L:C: expected IRI`).
- **Spike 3 result (RML test suite, full kg-construct/rml-test-cases):**
  Morph-KGC 87 / 324 pass (26.9%, 62% of testable cases),
  RMLMapper-Java 84 / 324 pass (25.9%), Maplib **0 / 324 pass.** Maplib
  errors on every test for the same root cause (stOTTR ≠ RML).
- **Spike 4 result (GTFS-Madrid-Bench mapping, synthetic-fallback on
  this host):** Morph-KGC materialises in 1.79 s / 254.9 MB RSS; Maplib
  fails before producing any triples. Output hashes diverge by
  construction (`maplib` triples = 0), so the speedup is not defined.

This is a **coverage-gate failure under the ADR-000 ranking** —
coverage outranks memory and performance. The speedup numbers below
are recorded only to show why they don't unblock the decision.

### Maturity
- Single-vendor (DataTreehouse). Smaller contributor base than the RMLio ecosystem behind Morph-KGC.
- Release cadence and issue-response times to be reported at acceptance.
- MappingLoom-RS, referenced in earlier drafts, was re-evaluated during
  Spike 3 and found to be a mapping-algebra translator (emits `.dot`
  plans, no RDF output) rather than a materialisation engine. Out of
  scope for L3.

### Memory
- Not measurable while Maplib cannot run the workload. Spike 4 records
  Morph-KGC's peak RSS (254.9 MB on the synthetic mapping at scale 1)
  so the harness is in place to compare against any future RML-capable
  candidate.

### Performance
- The "47×–182× faster than Morph-KGC" claim from the vendor's
  GTFS-Madrid-Bench writeup **cannot be reproduced** by Spike 4. There
  is no like-for-like comparison to make while Maplib refuses the
  mapping. Treat the published figure as unverifiable in this context
  until Maplib gains an RML ingestion path.

### Verdict
**Rejected for the L3 swap.** Maplib stays out of scope for ADR-004 §2.

- **Decision:** Keep Morph-KGC at L3. RMLMapper-Java is also a viable
  alternative if a JVM dependency is acceptable (within 1 pp of
  Morph-KGC on conformance, see Spike 3).
- **Re-open condition:** Maplib (or a successor) ships an RML→OTTR
  transpiler or a native RML reader that round-trips at least the
  kg-construct suite cases the hub depends on. At that point, re-run
  Spike 3 and Spike 4 unchanged; the harness is engine-agnostic.

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
2. **L3 ETL:** **Keep Morph-KGC.** Maplib is rejected at the coverage
   gate — it cannot ingest RML (Spikes 3 and 4). RMLMapper-Java is a
   recorded viable alternative if a JVM L3 dependency becomes desirable.
3. **L3 Virtualization:** **Keep ONTOP.** Chrontext is a different product, not a replacement.

If any spike fails, the corresponding incumbent stays.

## Consequences

- **Positive (if remaining L1/L2 spikes pass):**
  - Lower memory footprint at L1/L2 (magnitude TBD by benchmark, not assumed).
  - Fewer runtime dependencies in the container image at L1/L2.
- **At L3, no change to the operational picture:** Morph-KGC stays; the
  expected "faster ETL materialization" benefit at L3 does not
  materialise from this ADR.
- **Negative:**
  - Smaller upstream community than Jena at L1/L2. Higher bus-factor risk.
  - In-house expertise required for the new L1/L2 components; document
    operational runbooks before cutover.
  - ADR-001 is partially superseded on acceptance of L1/L2 only; ADR-002
    is **not** superseded — Morph-KGC remains the L3 ETL.

## Validation plan (must complete before status moves to Accepted)

1. **Oxigraph coverage spike:** enumerate Jena features in use; check each against Oxigraph. Output: feature-matrix table.
2. **Oxigraph benchmark:** bulk-load and query-mix benchmark on a representative dataset. Output: RSS, p50/p95 latency, load throughput vs. Jena/Fuseki.
3. **Maplib RML conformance:** ✅ **Done — Spike 3.** Maplib 0 / 324
   (no RML ingestion path); Morph-KGC 87 / 324, RMLMapper-Java 84 / 324.
   Coverage gate: fail.
4. **Maplib benchmark:** ✅ **Done — Spike 4.** Maplib fails on the
   GTFS-Madrid-Bench mapping for the same coverage reason; no
   like-for-like time/RSS comparison is possible. Morph-KGC baseline
   recorded for future RML-capable candidates.
5. **Scope decision on virtualization:** product owner confirms whether general SQL virtualization is in scope. If no, run Chrontext through the same gate; if yes, ONTOP stays and Chrontext is closed out.

## References

- [Oxigraph — GitHub](https://github.com/oxigraph/oxigraph)
- [Chrontext — GitHub](https://github.com/DataTreehouse/chrontext)
- [Maplib — GitHub](https://github.com/DataTreehouse/maplib)
- [W3C SPARQL 1.1 Test Suite](https://www.w3.org/2009/sparql/docs/tests/)
- [RML Test Cases](https://rml.io/test-cases/)
