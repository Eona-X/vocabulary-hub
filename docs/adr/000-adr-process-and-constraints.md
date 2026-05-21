# ADR-000: ADR Process, OSS Constraint, and ADR Layering

- **Status**: Accepted
- **Date**: 2026-05-21
- **Context**: eona_vocabulary_services project — establishing the decision-record process and the cross-cutting constraints that bind every subsequent ADR

## Context

The eona_vocabulary_services project implements an IDS-RAM 4.0 Vocabulary Hub. The reference vision is set out in David, Ivanov & Alexiev, *Raising the Role of Vocabulary Hubs for Semantic Data Interoperability in Dataspaces* (2024), which describes a hub built on GraphDB + PoolParty with an ONTOP-based Semantic Layer.

We treat that paper as **architectural guidance**: the roles, services, and layering it identifies (Vocabulary Hub core, Semantic Layer, mapping languages, KG-NLP, crosswalks, IDS conformance) are the target capabilities. We do not, however, adopt its specific product choices.

This ADR establishes:

1. That we use ADRs to record architectural decisions
2. The hard constraint that all building blocks must be OSI-approved open source
3. How subsequent ADRs are scoped and layered

## Decisions

### 1. We use ADRs

All non-trivial architectural decisions — choice of triplestore, mapping engine, authoring UI, pipeline framework, IDS adapter, deployment topology — are recorded as ADRs in `docs/adr/`.

- File name: `NNN-short-kebab-title.md`, three-digit zero-padded sequence
- Each ADR has: Status, Date, Context, Decision Drivers, Options Considered, Analysis, Recommendation, Consequences, References
- Status values: Proposed, Accepted, Superseded by ADR-NNN, Deprecated
- Revisions are appended in-place with a dated heading; the original reasoning is preserved (do not rewrite history)
- A superseded ADR is kept; the replacement ADR links back

### 2. OSI-licensed building blocks only

Every runtime component, library, and service we adopt must be released under an **OSI-approved license** (Apache-2.0, MIT, BSD, MPL-2.0, EPL-2.0, LGPL, GPL family, etc.). This is non-negotiable for the project scope.

Consequences:

- **Commercial-source products are out of scope as adopted components**, even when they have a free tier. The paper's GraphDB and PoolParty are in this category; their *roles* (scalable triplestore, vocabulary authoring + KG-NLP) remain in scope, but the implementations are not.
- Dual-licensed projects are acceptable if the OSI-licensed track meets our needs without feature gating that pushes us toward the commercial tier.
- "Source-available" licenses (BSL, SSPL, Elastic License, Confluent CL, etc.) are **not** OSS for this project's purposes.
- Build-time tooling and developer convenience tools are exempt from this constraint; only deployed artifacts and libraries we ship or depend on at runtime are bound.

Capabilities that no mature OSS component covers (e.g., PoolParty-class KG-NLP, GraphDB cluster) become *gaps to design around* — typically by composing smaller OSS pieces, accepting reduced scope, or enforcing the capability outside the affected layer (e.g., access control at the adapter rather than the triplestore).

### 3. ADRs are split by layer and purpose

To keep individual ADRs scoped and reviewable, decisions are partitioned along two axes:

**Layers** (vertical — what part of the stack):

| Layer | Concern | Example ADR topics |
|---|---|---|
| L1 — Storage | Persistent RDF, indexes, backups | Triplestore, mapping-asset store, blob storage |
| L2 — Semantic Services | Things the hub exposes as APIs | SPARQL endpoint, SHACL validation, reasoning, IRI dereferencing, semantic tagging, crosswalks, inference |
| L3 — Mapping / Virtualization | Binding heterogeneous data to vocabularies | ONTOP/OBDA, R2RML/RML, CSVW, mapping-asset lifecycle |
| L4 — Authoring & UI | Human-in-the-loop vocabulary management | SKOS/OWL editor, public browser, review workflow |
| L5 — IDS Conformance | Adapter, identity, protocol | IDS Information Model, EDC/DSC adapter, DAPS, Self-Description |
| L6 — Pipelines | Ingestion, transformation, scheduling | Query-service pipeline, batch materialization, validation gates |
| L7 — Platform | Cross-cutting runtime concerns | Reverse proxy, observability, auth, deployment topology |

**Purposes** (horizontal — what kind of decision):

- **Selection** — picking a specific component for a role (e.g., "use Fuseki for L1")
- **Integration** — how two chosen components talk (e.g., "EDC adapter reads from Fuseki via `RDFConnection`")
- **Policy** — cross-cutting rule (e.g., "every ingested ontology must pass SHACL before write")
- **Topology** — deployment shape (e.g., "adapter co-located in the JVM with triplestore")

Each ADR states its layer and purpose in the Context section so the catalogue stays navigable as it grows.

## Consequences

- **Positive**: Single source of truth for "why is X in the stack." OSS constraint is stated once, not relitigated per ADR. Layered structure makes it obvious where a new decision belongs and which ADRs it might supersede.
- **Negative**: Multiple smaller ADRs instead of one omnibus document; cross-references between ADRs become essential and require discipline.
- **Neutral**: The paper remains a reference for *roles and architecture*, not for *product choices*. ADRs may cite it as a source of requirements without inheriting its component selection.

## Initial ADR backlog (informational)

The following ADRs are anticipated but not yet written. Numbers will be assigned when authored.

| Topic | Layer | Notes |
|---|---|---|
| Triplestore selection | L1 | **ADR-001** (existing) — recommends Fuseki; revisit candidate list (RDF4J) under the OSS lens of this ADR |
| Semantic services engine selection | L2 | **ADR-002** (existing) — SHACL + reasoning + IRI dereferencing engines (extracted from original ADR-001) |
| Mapping & virtualization engine | L3 | **ADR-003** (existing) — ONTOP vs. RMLMapper vs. Morph-KGC; paper's Semantic Layer realized in OSS |
| Mapping-asset storage | L1/L3 | Where R2RML/OBDA/CSVW manifests live and how they are versioned |
| SHACL validation policy | L2/L6 | Ingestion-gate vs. runtime policy (engine selected in ADR-002) |
| Reasoning strategy | L2 | OWL profile choice, materialized vs. on-demand (engine selected in ADR-002) |
| Vocabulary authoring UI | L4 | VocBench 3, Skosmos, alternatives |
| Semantic tagging / KG-NLP | L2 | Annif and/or spaCy + DBpedia Spotlight as OSS substitutes for PoolParty's tagger |
| IDS adapter | L5 | EDC vs. DSC vs. Trusted Connector; co-location with triplestore |
| Ingestion pipeline | L6 | Current Python query-service; orchestration, idempotency, SHACL gating |
| Identity & access control | L5/L7 | DAPS, FGAC enforcement layer (adapter vs. proxy) |
| Deployment topology | L7 | Container layout, HA story under OSS constraints |

## References

- David, Ivanov & Alexiev, *Raising the Role of Vocabulary Hubs for Semantic Data Interoperability in Dataspaces* (2024)
- [OSI-approved licenses](https://opensource.org/licenses)
- [IDS-RAM 4.0 — Vocabulary Hub](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md)
- ADR-001 — Triplestore Selection (L1 Storage)
- ADR-002 — Semantic Services Engine Selection (L2)
