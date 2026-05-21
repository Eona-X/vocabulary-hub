# ADR-002: Semantic Services Engine Selection (L2)

- **Status**: Proposed
- **Date**: 2026-05-21 (extracted from the original [ADR-001](001-triplestore-stack-selection.md) which addressed both L1 and L2)
- **Layer / Purpose**: L2 Semantic Services — *selection*
- **Context**: eona_vocabulary_services SHACL validation engine, reasoning engine, and runtime IRI-dereferencing strategy
- **Binding constraints from [ADR-000](000-adr-process-and-constraints.md)**: OSI-licensed only.
- **Depends on**: [ADR-001](001-triplestore-stack-selection.md) — triplestore is Apache Jena Fuseki

## Context

The Vocabulary Hub exposes more than a SPARQL endpoint. It must also:

1. **Validate** ingested ontologies against SHACL shapes (ingestion gate + adapter-side runtime validation of Self-Descriptions)
2. **Reason** over RDFS/OWL — at minimum OWL 2 RL — so that dereferenced IRIs carry `rdf:type`, `rdfs:label`, `skos:definition` even when not explicitly asserted
3. **Dereference IRIs at runtime** for IDS Connectors that look up unknown resources, per [IDS-RAM 3.5.6](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md)

These are engine choices independent of the triplestore — the same Fuseki instance could be served by Jena's built-in SHACL/rules engines or by external Rust crates (rudof, reasonable) invoked from the pipeline.

ADR-001 selected Fuseki for storage on IDS-adapter co-location grounds. That choice cascades into the engine selection here, but the trade-offs deserve their own record because they are decided on different criteria (SHACL conformance, OWL profile coverage, hot-path latency).

## Decision Drivers (in priority order, per [feedback_adr_decision_drivers.md](../../.claude/projects/-home-nico-wspace-eona-vocabulary-hub/memory/feedback_adr_decision_drivers.md))

1. **Coverage** — SHACL Core vs Core+SPARQL; OWL 2 RL vs full DL
2. **Maturity** — W3C test-suite conformance, production users
3. **Memory** — engines run alongside the triplestore (steady or ingestion-time)
4. **Performance** — runtime vs batch; on-demand inference latency

Runtime language is **not** a driver, but cross-language *integration cost* with the IDS adapter is (because every Rust↔JVM hop is a serialization step on the IDS hot path — see ADR-001).

## Options Considered

### Option A: Jena-native services (SHACL + rule engine)

Use what ships with Fuseki / `jena-shacl` / `jena-arq`.

| Capability | Detail |
|---|---|
| SHACL | Apache Jena SHACL — Core + SPARQL-based constraints, W3C test-suite compliant |
| Reasoning | RDFS, OWL (built-in rule engine: OWL Micro/Mini/Full + custom rules); Pellet plugin available for DL |
| Runtime inference | Yes — Jena's rule engine can serve inferred triples on demand via `InfModel`/`OntModel` |
| Memory (with reasoning materialized) | 4–10 GB heap depending on ontology complexity (folded into Fuseki JVM) |
| Language | Java — same process as Fuseki and the EDC adapter |
| License | Apache 2.0 |

### Option B: Rust composable services (rudof + reasonable)

External Rust crates invoked from the pipeline (and/or as sidecars).

| Component | Role | Maturity | License |
|---|---|---|---|
| [rudof](https://github.com/rudof-project/rudof) | SHACL Core + ShEx validation | Academic-backed (WESO/ISWC 2024), CLI + lib + Python bindings | MIT |
| [reasonable](https://github.com/gtfierro/reasonable) | OWL 2 RL forward-chaining | Benchmarked: 7× faster than Allegro, 38× faster than OWLRL | MIT |

| Capability | Detail |
|---|---|
| SHACL | Core + ShEx; SPARQL-based constraints not covered |
| Reasoning | OWL 2 RL only (no full OWL-DL tableaux) |
| Runtime inference | **No** — `reasonable` is batch-only; on-demand inference requires querying pre-materialized graph |
| Memory | rudof: 30–80 MB per ingestion pass; reasonable: 50–150 MB per materialization run; both transient |
| Language | Rust — separate process from Fuseki/EDC |

### Option C: OxiRS bundled services

Reuse OxiRS's SHACL Core + SPARQL constraints (27/27 W3C tests) and RDFS/OWL/SWRL rule engine. Only meaningful if OxiRS is also chosen at L1 (ADR-001 rejected this on maturity grounds). Listed for completeness; not pursued separately.

## Analysis

```
                          SHACL coverage  OWL profile  Runtime inference  Adapter fit
Jena services (A)         Core+SPARQL     RDFS/OWL/DL  yes                in-process
Rust services (B)         Core+ShEx       OWL 2 RL     no (batch only)    cross-lang
OxiRS bundled  (C)        Core+SPARQL     RDFS/OWL/SWRL on roadmap        cross-lang
```

### Cross-language drift risk (B vs A)

If rudof handles ingestion-time SHACL but the IDS adapter must also validate Self-Descriptions at runtime (Java side), there are **two SHACL engines in the same system**. Subtle differences in how each interprets `sh:property` cardinality, `sh:qualifiedValueShape`, or SPARQL-based constraints will eventually produce divergent verdicts. The mitigation cost is non-trivial (cross-engine conformance tests in CI; see B.2 cost row below).

### Runtime reasoning is load-bearing for IRI dereferencing

The IDS Vocabulary Hub spec implies that a Connector resolving an unknown IRI must receive `rdf:type` and label/definition triples in the response. If reasoning is batch-only:

- Every ontology edit forces a full re-materialization before changes are visible
- The triplestore grows with the inferred closure (multiplies storage cost)
- No way to serve `owl:sameAs` or class-equivalence consequences for IRIs added since the last batch

Jena's runtime rule engine sidesteps all three.

## Recommendation

**Option A — Jena-native SHACL + rule engine**, served from the same JVM as Fuseki.

Rationale (engine-layer specific):

1. **One SHACL engine of record**: Used both at the ingestion gate (replacing rudof) and at runtime by the IDS adapter when validating Self-Descriptions. Eliminates cross-language drift.
2. **Runtime inference**: The Vocabulary Hub's IRI-dereferencing contract requires on-demand `rdf:type`/`label`/`definition`. Only Jena's rule engine supports this without batch re-materialization.
3. **Coverage**: SHACL-SPARQL (needed for any non-trivial constraint over multiple shapes) is in Jena, not in rudof.
4. **OWL profile headroom**: OWL 2 RL is enough for vocabulary class hierarchies today, but Jena keeps the door open for OWL-DL via Pellet if richer reasoning is ever required.
5. **No new processes**: Reasoning and SHACL run in the Fuseki JVM; no Rust sidecar to operate, no IPC.

### When to revisit

- A Rust SHACL engine reaches SHACL-SPARQL conformance *and* the IDS adapter ecosystem ships a Rust track
- Runtime reasoning latency becomes a measured bottleneck (then evaluate pre-materializing the OWL 2 RL closure with `reasonable` as a write-side step into Fuseki)
- The hub adopts ShEx for community-authored shapes (rudof becomes interesting again as an ingestion-time engine alongside Jena SHACL)

### Implementation path

1. **Phase 1** — Expose Jena SHACL through the query-service pipeline as an ingestion gate; reject `.ttl` files that fail validation.
2. **Phase 2** — Enable Jena's rule engine on the public-facing dataset so IRI dereferencing serves inferred triples. Start with RDFS + OWL Mini; tune per measured ontology cost.
3. **Phase 3** — Once the EDC adapter is in place (ADR-005 backlog), have it reuse the same `Shapes` graph for runtime Self-Description validation.
4. **Phase 4** — If runtime reasoning cost is excessive, switch the public dataset to a materialized inference model refreshed on write.

## Cost estimate for the Rust-services variant (Option B)

If Option B is ever reconsidered, the engineering cost is dominated by the IDS adapter glue, not by the SHACL/reasoning code itself. Three paths exist; numbers are person-months (PM) of a senior engineer fluent in both Rust and Java/IDS, assuming access to the IDS-Testbed.

### B.1 — Pure Rust services + hand-written Rust IDS adapter

Reimplement IDS Information Model + DAPS + Multipart in Rust to keep the stack single-language.

| Work item | Estimate | Risk |
|---|---|---|
| Port `de.fraunhofer.iais.eis.ids.infomodel` types and JSON-LD framing to Rust | 6 – 12 PM | High — ~500 IM classes; framing rules subtle; no starting crate |
| IDS Multipart message handler | 1 – 2 PM | Medium |
| DAPS DAT validation (JWT + JWKS rotation + claim mapping) | 0.5 PM | Low |
| Self-Description generation from SPARQL | 1 – 2 PM | Medium |
| IRI dereferencing with type inference (replacement for Jena rules) | 2 – 3 PM | High — `reasonable` is batch-only |
| Conformance testing against IDS-Testbed + EDC peer | 2 – 3 PM | High |
| Ongoing maintenance per IDS Infomodel revision | 1 – 2 PM / year | Medium |
| **Initial total** | **~13 – 22 PM** | ~1.5 FTE-years |
| **Steady-state** | **~1 – 2 PM / year** | |

Loaded cost at €12–18k/PM: **initial €160k – €400k**, plus €15k – €35k/year.

### B.2 — Rust services + off-the-shelf JVM IDS adapter (EDC over HTTP)

The "honest" Option B — accepts that the IDS adapter must be JVM.

| Work item | Estimate | Risk |
|---|---|---|
| Deploy and configure EDC connector | 0.5 – 1 PM | Low |
| EDC extension sourcing vocabulary catalogue from store | 1 – 2 PM | Medium |
| Self-Description bridge: SPARQL → Jena `Model` → `infomodel.jar` | 0.5 – 1 PM | Medium |
| Cache layer to keep SPARQL→Model translation off the hot path | 0.5 – 1 PM | Low |
| Adapt query-service pipeline; add rudof SHACL gate | 1 PM | Low |
| Add `reasonable` materialization step | 0.5 – 1 PM | Low |
| Cross-language conformance tests (rudof vs Jena SHACL drift) | 0.5 – 1 PM | Medium |
| **Initial total** | **~4.5 – 8 PM** | ~0.5 – 0.7 FTE-years |
| **Steady-state** | **~0.5 PM / year** | dual-language ops overhead |

Loaded cost: **initial €55k – €145k**, plus ~€7k – €9k/year.

### B.3 — Rust storage behind a JVM façade

Use Oxigraph only as a storage detail accessed by the JVM, with Jena providing SPARQL + SHACL + reasoning on top.

| Work item | Estimate |
|---|---|
| Wrap Oxigraph behind a Jena-compatible `Dataset` | 3 – 5 PM (high risk, low value) |
| Everything else from B.2 | 4 – 7 PM |
| **Initial total** | **~7 – 12 PM** |

**Not recommended** — fights both ecosystems; listed for completeness.

### Summary table

| Path | Initial PM | Initial € | Annual maint. | Risk |
|---|---|---|---|---|
| A — Jena services (this ADR) | ~2 – 3 PM | €25k – €55k | ~0.2 PM/year | Low |
| B.1 — pure Rust services + Rust adapter | ~13 – 22 PM | €160k – €400k | ~1 – 2 PM/year | High |
| B.2 — Rust services + JVM adapter | ~4.5 – 8 PM | €55k – €145k | ~0.5 PM/year | Medium |
| B.3 — Rust storage behind JVM façade | ~7 – 12 PM | €85k – €215k | ~0.5 PM/year | Medium-High |

Even the cheapest Rust path (B.2) is ~2× the initial cost of Option A for the engine layer, in exchange for a SHACL/reasoning surface that is strictly less capable (no SHACL-SPARQL, no runtime inference).

## Consequences

- **Positive**: Single SHACL engine across ingestion and runtime; runtime reasoning available for IRI dereferencing; no Rust sidecars to operate; engine evolution tracks the same Jena release cadence as the triplestore.
- **Negative**: Reasoning cost is paid in the Fuseki JVM heap (rising into the 4–10 GB range with materialized OWL closures over complex ontologies); no path to the lighter Rust validation footprint.
- **Neutral**: rudof and reasonable remain available as developer tools and benchmarking baselines; this ADR does not forbid their use in CI or in offline analysis.

## References

- [Apache Jena SHACL](https://jena.apache.org/documentation/shacl/)
- [Apache Jena Inference / rule engine](https://jena.apache.org/documentation/inference/)
- [rudof — GitHub](https://github.com/rudof-project/rudof)
- [rudof ISWC 2024 paper](https://ceur-ws.org/Vol-3828/paper32.pdf)
- [reasonable — GitHub](https://github.com/gtfierro/reasonable)
- [IDS-RAM 4.0 — Vocabulary Hub](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md)
- [ADR-001](001-triplestore-stack-selection.md) — Triplestore selection (L1)
