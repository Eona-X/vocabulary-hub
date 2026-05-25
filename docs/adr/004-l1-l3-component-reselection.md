# ADR-004: Re-selecting L1–L3 Components — Oxigraph, Maplib, Chrontext

- **Status**: Accepted (§1 accepted; §2 rejected; §3 conditional on Spike 5 outcome)
- **Date**: 2026-05-25 (accepted); 2026-05-21 (proposed)
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

### Coverage — **passes the gate** (see Spike 1)

- SPARQL 1.1 Query and Update: confirmed on Oxigraph 0.5.8 — SELECT / CONSTRUCT / ASK / DESCRIBE / UPDATE-INSERT / UPDATE-DELETE all pass the auto-probed coverage matrix.
- RDF 1.1 (named graphs, datasets): supported.
- Content negotiation: Turtle, **JSON-LD**, N-Triples, RDF/XML, TriG all pass — the prior 0.4.7 JSON-LD CONSTRUCT gap is closed on 0.5.8. No API-layer JSON-LD transcoding workaround is required.
- Federation (`SERVICE`): the only failing probe on Oxigraph; the same probe also fails on Fuseki 5.1.0 in the sandbox — network-bound, not engine-bound. Working assumption: not a documented hub requirement. To be confirmed by product owner.
- SHACL, OWL 2 RL runtime inference, RDFS entailment, persistence-restart, HTTP auth: out of scope for L1/L2 (belong to ADR-002 companion components or deployment hardening).

Spike 1 verdict: **18 / 20 pass on both engines**, parity with Fuseki. Coverage gate passed.

### Maturity
- Tagged releases, semantic versioning, active maintenance (verify last-release cadence at acceptance time).
- Governance: maintained primarily by Tpt; smaller contributor base than Jena. Bus factor is a real risk and should be acknowledged.
- Production deployments: list known users before claiming "production maturity."

### Memory — **passes the gate** (see Spike 2)

- Peak RSS on the deployment-realistic (on-disk) variant: Oxigraph **173 MB** vs Fuseki **1272 MB** — **~7.34×** lower, not the 10× claimed in earlier drafts. The "10× memory" framing is corrected to **~7× memory** on a 100k-triple synthetic SKOS workload.

### Performance — **passes the gate** (see Spike 2)

- Bulk load (100k triples): Oxigraph **166 966 t/s** vs Fuseki **162 200 t/s** — effectively tied; the prior 5.9× Fuseki advantage was an in-memory-vs-RocksDB artefact.
- UPDATE INSERT (`q07`): Oxigraph 1.1 ms vs Fuseki 45.3 ms — **~41×** faster. Material for an ingestion-on-publish hub.
- Property-path and CONSTRUCT shapes (`q02`, `q04`, `q08`): 3–4× in Oxigraph's favour.
- **Known regression:** cross-named-graph COUNT (`q06`) is **5.5× slower** on Oxigraph 0.5.8 than on Jena 5.1.0 (24.7 ms vs 4.5 ms). Tracked as an upstream Oxigraph query-planner issue; not a deployment blocker.
- Label-scan with FILTER (`q01`): 2× Fuseki edge after Jena 5.1.0's ARQ improvements. Acceptable.

Caveats: public-reference workload, single-threaded client, single 100k-triple dataset, no SHACL/reasoning load layered on top.

### Embedding note (not a driver, but operationally relevant)
ADR-001 made co-location with the IDS adapter a driver because Jena `Model` objects were passed in-process to the Java EDC. If L5 stays on EDC (per the scope exclusion above), Oxigraph would sit behind an HTTP boundary and the previous in-process argument no longer favors Jena — but it also doesn't favor Oxigraph. Neutral.

### Verdict
**Accepted.** Spike 1 (coverage) and Spike 2 (memory + performance) both pass on Oxigraph 0.5.8 / Jena 5.1.0. Pin the production deployment to **Oxigraph ≥ 0.5.8** and, where Fuseki survives at all, **Apache Jena ≥ 5.1.0**.

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
**Conditional — gated on Spike 5 scope decision (product owner, open).** Working hypothesis from [`spikes/05_virtualization_scope/decision.md`](../../spikes/05_virtualization_scope/decision.md): the documented hub requirements (IDS-RAM §3.5.6, ADR-001 §Required capabilities, ADR-002) do not mandate relational virtualization. Default close: "L3 virtualization not required; both ONTOP and Chrontext out of scope," with ADR-003 revised to drop the virtualization half. If the product owner identifies a concrete time-series-join use case, Chrontext re-enters as a candidate and runs the same coverage/maturity/memory/perf gate as Spikes 1–4. If a general SQL virtualization use case lands, ONTOP stays.

---

## Decision

1. **L1/L2:** **Replace Jena/Fuseki with Oxigraph.** Spikes 1 and 2 pass. Pin Oxigraph ≥ 0.5.8 and Jena ≥ 5.1.0 (for any surviving Fuseki). File the Oxigraph cross-named-graph COUNT regression (`q06`) upstream and track for resolution.
2. **L3 ETL:** **Keep Morph-KGC.** Maplib is rejected at the coverage gate — it cannot ingest RML (Spikes 3 and 4). RMLMapper-Java is a recorded viable alternative if a JVM L3 dependency becomes desirable.
3. **L3 Virtualization:** **Hold — pending Spike 5 product-owner decision.** Default close, if no answer lands before the next ADR review, is "L3 virtualization not required; both ONTOP and Chrontext out of scope" with ADR-003 revised accordingly. Until then, ONTOP nominally remains.

A consolidated read of the five spikes is in [`spikes/SYNTHESIS.md`](../../spikes/SYNTHESIS.md).

## Consequences

- **Positive (L1/L2):**
  - Peak RSS down ~7× on the deployment-realistic variant (Spike 2: 173 MB vs 1272 MB on 100k triples).
  - Bulk load tied with Fuseki; UPDATE INSERT ~41× faster — material for an ingestion-on-publish hub.
  - Fewer runtime dependencies in the container image at L1/L2 (no JVM).
  - JSON-LD CONSTRUCT works natively on Oxigraph 0.5.8 — no API-layer transcoding workaround needed.
- **At L3, no change to the operational picture:** Morph-KGC stays; the expected "faster ETL materialization" benefit at L3 does not materialise from this ADR.
- **Negative:**
  - Smaller upstream community than Jena at L1/L2. Higher bus-factor risk.
  - In-house expertise required for the new L1/L2 components; document operational runbooks before cutover.
  - Cross-named-graph COUNT (`q06`) is ~5.5× slower on Oxigraph than on Jena 5.1.0 — file upstream and monitor.
  - ADR-001 is partially superseded on acceptance of L1/L2 only; ADR-002 is **not** superseded — Morph-KGC remains the L3 ETL.
  - ADR-003 to be revised conditional on Spike 5 if the virtualization-scope default close stands.

## Validation plan

1. **Oxigraph coverage spike:** ✅ **Done — Spike 1.** Oxigraph 0.5.8: 18 / 20 pass (parity with Fuseki 5.1.0). JSON-LD gap closed. Coverage gate: pass.
2. **Oxigraph benchmark:** ✅ **Done — Spike 2.** Disk variant — RSS 173 MB vs 1272 MB (~7×), bulk-load tied at ~165k t/s, UPDATE INSERT ~41× faster, `q06` cross-named-graph COUNT 5.5× slower on Oxigraph (upstream issue to file). Memory + performance gates: pass.
3. **Maplib RML conformance:** ✅ **Done — Spike 3.** Maplib 0 / 324 (no RML ingestion path); Morph-KGC 87 / 324, RMLMapper-Java 84 / 324. Coverage gate: fail.
4. **Maplib benchmark:** ✅ **Done — Spike 4.** Maplib fails on the GTFS-Madrid-Bench mapping for the same coverage reason; no like-for-like time/RSS comparison is possible. Morph-KGC baseline recorded for future RML-capable candidates.
5. **Scope decision on virtualization:** ⏸ **Open — Spike 5.** Awaiting product-owner input. Default close, if no use case is identified, is "L3 virtualization not required" with ADR-003 revised accordingly.

## References

- [Oxigraph — GitHub](https://github.com/oxigraph/oxigraph)
- [Chrontext — GitHub](https://github.com/DataTreehouse/chrontext)
- [Maplib — GitHub](https://github.com/DataTreehouse/maplib)
- [W3C SPARQL 1.1 Test Suite](https://www.w3.org/2009/sparql/docs/tests/)
- [RML Test Cases](https://rml.io/test-cases/)
