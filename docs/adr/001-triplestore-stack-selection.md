# ADR-001: Triplestore Selection (L1 Storage)

- **Status**: Proposed (revised 2026-05-18 — IDS Vocabulary Hub conformance added as a hard requirement; revised 2026-05-21 — re-scoped under [ADR-000](000-adr-process-and-constraints.md) and split: semantic-services concerns extracted to [ADR-002](002-semantic-services-engine-selection.md))
- **Date**: 2026-05-11
- **Layer / Purpose**: L1 Storage — *selection*
- **Context**: eona_vocabulary_services persistent RDF store and SPARQL 1.1 endpoint
- **Binding constraints from [ADR-000](000-adr-process-and-constraints.md)**: OSI-licensed building blocks only; the David/Ivanov/Alexiev (2024) paper is a guide for *roles and architecture*, not for *product choices*. GraphDB and PoolParty are therefore not candidates here.
- **Related**: [ADR-002](002-semantic-services-engine-selection.md) decides the SHACL/reasoning/IRI-dereferencing engines that sit on top of the store selected here.

## Context

The semantic-hub currently runs **Apache Jena Fuseki** (`stain/jena-fuseki:latest`) as its triplestore and SPARQL endpoint, fronted by Traefik, with a Python-based query-service pipeline that populates the store from `.ttl` files.

This ADR is restricted to the **persistence + SPARQL endpoint** role. SHACL validation, reasoning, and runtime IRI dereferencing — all of which several of the candidates also implement — are evaluated in ADR-002.

Requirements for the storage layer:

1. **SPARQL 1.1** query and update
2. **Open source** licensing (OSI-approved)
3. **Low memory footprint** suitable for edge/small-cluster deployment
4. **IDS-RAM 4.0 Vocabulary Hub conformance** (added 2026-05-18) — the IDS adapter (see ADR-005 backlog) must be able to reach the store cheaply; per [IDS-RAM 3.5.6](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md), the hub must serve IDS Information Model JSON-LD on the hot path.

## Decision Drivers

- Current Fuseki deployment has no `-Xmx` tuning, defaulting to JVM ergonomics (~25% of host RAM)
- The query-service pipeline does full drop-and-reload; we don't rely on incremental transaction guarantees
- Docker image size and cold-start time matter for CI and edge deployment
- The IDS adapter ecosystem is overwhelmingly JVM (EDC, DSC, Trusted Connector, `infomodel.jar`); cross-language RDF hand-off has a real cost on every IDS message

## Options Considered

### Option A: Apache Jena Fuseki (Java, incumbent)

| Aspect | Detail |
|---|---|
| SPARQL | Full 1.1 (query, update, federation, graph store protocol) |
| Docker image | ~500–700 MB |
| Memory (idle, ~1M triples) | 512 MB – 1 GB heap minimum; typical production 2–4 GB `-Xmx` |
| Cold start | 5–15s (JVM warmup + TDB2 journal replay) |
| License | Apache 2.0 |
| IDS adapter integration | In-process embedding possible — Jena is a Java library; an EDC extension can call `RDFConnection` directly with zero network hop. Same `Model` API used by `infomodel.jar`. |

**Total estimated RSS for the Fuseki service: 1.5 – 4 GB.**

### Option B: Oxigraph (Rust)

[Oxigraph](https://github.com/oxigraph/oxigraph) — RocksDB-backed Rust triplestore with near-full SPARQL 1.1.

| Aspect | Detail |
|---|---|
| SPARQL | Near-full 1.1; federation partial |
| Docker image | ~20–50 MB (static Rust binary) |
| Memory (~1M triples) | 80–200 MB RSS; no JVM, no GC, memory-mapped SSTs |
| Cold start | < 1s |
| License | MIT / Apache 2.0 |
| Maturity | Actively maintained since 2019; multiple production users |
| IDS adapter integration | Not in-process from JVM; adapter must reach Oxigraph over HTTP SPARQL/Graph Store API. Adapter holds Jena `Model`s; Oxigraph holds Oxrdf quads → translation at every IDS message. |

### Option C: OxiRS (Rust, all-in-one)

[OxiRS](https://github.com/cool-japan/oxirs) — monolithic Rust replacement for the Jena stack.

| Aspect | Detail |
|---|---|
| SPARQL | 1.1 + 1.2 draft features |
| Docker image | ~30–60 MB (estimated) |
| Memory | Comparable to Oxigraph (same RocksDB foundations) |
| Maturity | v0.1.0 production release Jan 2026; small community, less independently validated |
| License | MIT |
| IDS adapter integration | Same cross-language penalty as Option B |

## Analysis

```
                  Maturity  Memory  SPARQL 1.1  Image  IDS-adapter fit
Fuseki (A)        *****     **      *****       **     *****
Oxigraph (B)      ****      *****   ****        *****  **
OxiRS (C)         **        *****   *****       *****  **
```

### Re-scoring with the IDS adapter co-deployed

The IDS adapter (EDC-class, JVM, ~500 MB – 1 GB heap) is mandatory regardless of triplestore choice (see ADR-005 backlog; Rust IDS tooling exists only as research prototypes).

| Stack | Triplestore RSS | Adapter RSS | Total steady-state | Ops surface |
|---|---|---|---|---|
| **A. Fuseki + EDC adapter** | 1.5 – 4 GB (JVM) | 0.5 – 1 GB (JVM) | **2 – 5 GB** | One language (Java), two JVMs to tune |
| **B. Oxigraph + EDC adapter** | 80 – 200 MB | 0.5 – 1 GB (JVM) | **0.6 – 1.2 GB** | Two languages (Rust + Java), one JVM |
| **C. OxiRS + EDC adapter** | 100 – 250 MB | 0.5 – 1 GB (JVM) | **0.6 – 1.3 GB** | Two languages, one JVM, lower triplestore maturity |

The Rust memory advantage **survives** the addition of an IDS adapter (B is ~3× lighter than A). But the *operational simplification* argument for Rust weakens — the stack is no longer "single static binary" once the adapter is present.

The dominant cost the original ADR understated: **every byte that crosses the Rust ↔ JVM boundary is a serialization step**. For a vocabulary hub whose entire purpose is shipping RDF to clients, that boundary sits on the hot path.

## Recommendation (revised 2026-05-18)

**Option A — stay on Apache Jena Fuseki.**

Rationale (storage-layer specific):

1. **IDS adapter co-location**: An EDC/DSC-class adapter is mandatory and JVM-based. Co-locating it with a JVM triplestore lets the adapter use Jena's `Model`/`RDFConnection` in-process, sharing the IDS Information Model object graph with `infomodel.jar` natively.
2. **No cross-language translation on the hot path**: Every dereferenced IRI, every Self-Description response, every Description/Artifact message would otherwise serialize from Oxrdf → JSON-LD → Jena `Model`.
3. **Operational reality**: The "single static binary" pitch evaporates once the JVM adapter is present. The Rust stack's wins are now ~3× memory and faster cold-start — real, but no longer transformational against a 2–5 GB baseline that is already small for a Kubernetes deployment.
4. **Risk asymmetry**: Re-architecting *and* adopting IDS conformance simultaneously doubles the risk surface. Fuseki + IDS adapter is one new moving part; Oxigraph + IDS adapter + cross-language serialization is three.

Engine-level concerns (SHACL, reasoning) that *also* favor Jena are decided in [ADR-002](002-semantic-services-engine-selection.md).

### When to revisit

- A production-quality Rust IDS Information Model library appears (crates targeting `ids:` JSON-LD framing and IDSCP2)
- EDC publishes an officially supported Rust extension SDK
- OxiRS reaches v1.0 with demonstrated EDC integration
- Deployment target shifts to severely memory-constrained edge (< 1 GB total) where 3× matters
- **A second OSS-JVM candidate evaluation is requested** — notably **Eclipse RDF4J** (BSD), which shares Fuseki's JVM co-location advantage and is the lineage of the Fraunhofer Dataspace Connector

### Migration / hardening path (storage layer only)

1. **Phase 0 (immediate)** — Tune the existing Fuseki: explicit `-Xmx` (start at 1 GB), enable TDB2, document backup/restore procedure.
2. **Phase 1** — Expose Fuseki only via the reverse proxy and the adapter; remove any direct public SPARQL endpoint exposure once the adapter handles authenticated access.

Semantic-services hardening (SHACL gate, runtime reasoning) is sequenced in ADR-002.

## Cost note (storage layer)

A Rust triplestore swap on its own is cheap (~1 PM to migrate the load pipeline to Oxigraph HTTP); the cost lives in what sits on top of it. See [ADR-002](002-semantic-services-engine-selection.md) for the engine-level cost analysis and the full Option B variant breakdown (B.1 pure Rust, B.2 Rust store + JVM adapter, B.3 Oxigraph as embedded storage).

Infrastructure savings of Option B vs A are ~3 GB RSS per replica ≈ **€1.3k/year** at commodity rates — never the deciding factor.

## Consequences

- **Positive**: Lowest-risk path to IDS-RAM Vocabulary Hub conformance at the storage layer; in-process integration with `infomodel.jar` and EDC; no cross-language RDF translation on the hot path.
- **Negative**: Memory footprint stays at JVM scale; container images stay large; project remains JVM-centric, which constrains future hires/contributors who prefer Rust/Go.
- **Neutral**: License posture unchanged; the Rust stack remains a viable fallback if the JVM operational cost ever becomes the dominant constraint.

## References

- [Oxigraph — GitHub](https://github.com/oxigraph/oxigraph)
- [OxiRS — GitHub](https://github.com/cool-japan/oxirs)
- [Oxigraph evaluation paper (2023)](https://www.researchgate.net/publication/372104813_Evaluating_Oxigraph_Server_as_a_triple_store_for_small_and_medium-sized_datasets)
- [Fuseki memory discussions — Jena mailing list](https://www.mail-archive.com/users@jena.apache.org/msg20711.html)
- [IDS-RAM 4.0 — Vocabulary Hub](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md)
