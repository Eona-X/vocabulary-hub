# ADR-003: Mapping and Virtualization Engine

- **Status**: Proposed
- **Date**: 2026-05-21
- **Layer / Purpose**: L3 Mapping / Virtualization — *selection*
- **Context**: eona_vocabulary_services Semantic Layer — binding heterogeneous source data (relational, tabular, document) to vocabularies managed by the hub
- **Binding constraints from [ADR-000](000-adr-process-and-constraints.md)**: OSI-licensed only. Paper (David/Ivanov/Alexiev 2024) treated as guidance; its choice of ONTOP for OBDA is a hint to evaluate, not to adopt by default.
- **Depends on**: [ADR-001](001-triplestore-stack-selection.md) — triplestore is Apache Jena Fuseki

## Context

The paper's Semantic Layer is the project's largest open scope. It binds incoming datasets to managed vocabularies via standardized mapping languages, in two flavors:

- **NoETL (virtualization)** — leave data at the source, translate SPARQL → source-native query (typically SQL) on demand. Critical for large time-series and frequently-updated relational data where copying into RDF is impractical.
- **ETL (materialization)** — transform once into RDF, store in the triplestore, query natively. Right answer for static/slowly-changing reference data, denormalized views, and file-based sources.

Source types we expect (paper §2 + project scope):

| Source kind | Examples | Likely mode |
|---|---|---|
| Relational DB | PostgreSQL, MySQL | NoETL preferred |
| Time series DB | InfluxDB | NoETL (volume) |
| Cloud warehouses | BigQuery | NoETL |
| Tabular files | CSV from connectors | ETL via CSVW or RML |
| Semi-structured | JSON, XML | ETL via RML |

Mapping languages in scope (all W3C/community standards, all OSI-supported):

- **R2RML** — W3C Rec, RDB → RDF, mature, multiple engines
- **OBDA** (`.obda` syntax) — ONTOP's compact mapping language; convertible to/from R2RML
- **RML** — RDF Mapping Language, generalizes R2RML to CSV/JSON/XML; de-facto community standard
- **CSVW** — W3C Rec for tabular data on the web; JSON manifest + CSV

## Decision Drivers

Ranked. Functional coverage and maturity gate the field; runtime characteristics decide between qualifying candidates. Runtime language is **not** a driver at this layer.

1. **Functional coverage** — cover both NoETL and ETL; support at minimum R2RML + RML + CSVW (OBDA accepted as an ONTOP-native dialect that round-trips with R2RML).
2. **Maturity** — at least one release in the last 18 months, responsive issue tracker, production references.
3. **Memory footprint** — engines run in the ingestion path; per-run RSS matters for container sizing and parallelism.
4. **Performance** — throughput on realistic input sizes (relational tables in the 10⁶–10⁸ row range; CSV files in the 100 MB – 10 GB range).
5. **Mapping-asset lifecycle** — engines must accept mappings as files or strings so mappings stored in the hub (separate ADR) can be loaded at runtime without rebuilds.
6. **Independent operation** — engine must be invokable as a service or library independently of the triplestore (Fuseki) so it can be swapped or scaled separately.

## Options Considered

Engines listed below are all OSI-licensed and actively maintained.

### NoETL / virtualization candidates

| Engine | License | Mapping langs | Sources | Notes |
|---|---|---|---|---|
| **ONTOP** | Apache-2.0 | OBDA, R2RML | RDBMS via JDBC (PostgreSQL, MySQL, Oracle, MSSQL, Denodo, etc.) | The paper's choice. Mature SPARQL-to-SQL rewriter; query optimization is its key differentiator. Standalone CLI, Jena/RDF4J wrappers, embedded library |
| **Morph-RDB** | Apache-2.0 | R2RML | RDBMS | Older OEG/UPM project; ONTOP's predecessor in spirit; less actively maintained than ONTOP |
| **D2RQ** | Apache-2.0 | D2RQ mapping (R2RML-like) | RDBMS | Legacy, effectively unmaintained — disqualified by driver #5 |

**ONTOP wins on NoETL.** It is the only OSS engine combining maintained status, strong SPARQL-to-SQL optimization, R2RML+OBDA support, and broad JDBC reach.

### ETL / materialization candidates

| Engine | License | Mapping langs | Sources | Notes |
|---|---|---|---|---|
| **RMLMapper** | MIT (Ghent IDLab) | RML, R2RML | CSV, JSON, XML, RDB, web APIs | Java; the RML reference implementation; correct but slow on large inputs |
| **Morph-KGC** | Apache-2.0 (UPM) | RML, R2RML, RML-star | CSV, JSON, XML, Parquet, RDB | Python; partition-based parallel execution, the fastest open engine in recent KGC benchmarks; supports RDF-star |
| **SDM-RDFizer** | Apache-2.0 | RML | CSV, JSON, XML, RDB | Python; optimized for joins; widely used in life-sciences pipelines |
| **CARML** | MIT (Taxonic) | RML | CSV, JSON, XML | Java; library-friendly; smaller community |
| **Jena R2RML** | Apache-2.0 | R2RML (partial) | RDBMS | Bundled with Jena; basic, no RML |

**Two strong candidates: RMLMapper (Java, reference) and Morph-KGC (Python, fastest).** RMLMapper aligns with the JVM stack; Morph-KGC wins on throughput and language coverage (RML-star, Parquet).

### CSVW candidates

| Engine | License | Notes |
|---|---|---|
| **csv2rdf** (Swirrl) | Eclipse-2.0 | Clojure; W3C CSVW reference-ish behavior |
| **csvwlib** | MIT | Python; CSVW → RDF |
| **RMLMapper / Morph-KGC** | — | CSVW can be expressed as RML; using one engine for CSV + JSON + XML reduces tooling surface |

CSVW is narrow enough that we can either keep a dedicated converter or fold CSV handling into the RML engine via CSVW-to-RML translation.

## Analysis

No single OSS engine covers the full matrix (NoETL + ETL + RML + R2RML + CSVW). A composed solution is unavoidable:

```
                NoETL (RDB)       ETL (files)        ETL (RDB)         CSVW
ONTOP             ✓ (primary)        —                 —                 —
RMLMapper         —                  ✓                 ✓ (slow)          via RML
Morph-KGC         —                  ✓ (fast)          ✓                 via RML
```

The choice on the ETL side is **RMLMapper vs Morph-KGC**. Both meet functional coverage and maturity bars. They differ on runtime characteristics:

| | RMLMapper | Morph-KGC |
|---|---|---|
| Per-run RSS (10⁶ triples) | ~1–2 GB (JVM heap) | ~200–500 MB |
| Throughput on large CSV/JSON | reference-correct, single-threaded | partitioned, multi-process; ~5–10× faster on KGC benchmarks |
| RML-star, Parquet | no | yes |

Both run as separate pipeline-invoked processes; neither is co-located with Fuseki or the IDS adapter. Runtime language is therefore not a selection criterion at this layer — operations sees a container with a binary entry point in either case.

## Recommendation

Adopt a **two-engine composition**:

1. **ONTOP** for NoETL virtualization of relational and warehouse sources.
   - Exposed as a sidecar SPARQL endpoint to which the hub federates relevant subqueries
   - Mappings authored in OBDA syntax (compact) or R2RML (portable); both can be stored as mapping assets in the hub
2. **Morph-KGC** for ETL materialization of file-based and selected relational sources.
   - Invoked from the ingestion pipeline (L6) on a schedule or event
   - Output RDF written to Fuseki via SPARQL Update / Graph Store Protocol
   - Chosen over RMLMapper on **memory footprint** (~3–5× lower per run) and **throughput** (~5–10× on large CSV/JSON inputs); functional coverage and maturity are comparable, with Morph-KGC additionally supporting RML-star and Parquet

**CSVW** is handled via Morph-KGC's RML path (CSVW manifest translated to RML on ingest) rather than maintaining a third engine. A dedicated `csv2rdf` is allowed as an escape hatch for strict W3C CSVW conformance if a use case demands it.

### Why not ONTOP only

ONTOP does not handle file sources, JSON, or XML and is not designed for materialization. Forcing CSV through ONTOP via a federated wrapper has been tried and is fragile.

### Why not RMLMapper only / Morph-KGC only

Neither does NoETL. Materializing every relational and time-series source defeats the paper's core argument for a Semantic Layer (keep big data at the source).

### Why not RMLMapper on the ETL side

RMLMapper is the RML reference implementation and is functionally adequate. It loses to Morph-KGC on the runtime drivers (#3, #4): higher per-run memory and materially lower throughput on the input sizes we expect. There is no operational simplification to offset this — both engines run as separate pipeline-invoked containers regardless of implementation language.

## Consequences

- **Positive**:
  - Full coverage of the paper's mapping-language matrix in OSS (R2RML, OBDA, RML, CSVW)
  - NoETL path preserves data sovereignty (source data not copied into the hub)
  - Engines run independently and can be scaled or replaced without touching Fuseki or the IDS adapter
  - Mappings are portable: ONTOP↔R2RML and CSVW↔RML conversions are well-defined
- **Negative**:
  - Two engines to operate, each with its own runtime and packaging
  - Federated queries that cross ONTOP and Fuseki require SPARQL 1.1 federation; performance is workload-dependent
  - Mapping-asset storage and versioning is now a real requirement, not optional — needs its own ADR
- **Neutral**:
  - The IDS adapter still talks SPARQL; the Semantic Layer is largely invisible to it except via federated queries

## Open questions deferred to other ADRs

| Question | Owning ADR |
|---|---|
| Where do mapping assets live (file system, Fuseki graph, Git repo)? | Mapping-asset storage (L1) |
| How are mappings validated before deployment? | Mapping validation policy (L6) |
| How does the ingestion pipeline orchestrate Morph-KGC runs and incremental updates? | Ingestion pipeline (L6) |
| Federation topology: Fuseki-as-gateway vs client-side federation | SPARQL federation (L2) |

## References

- David, Ivanov & Alexiev (2024) §4 — Semantic Layer approach
- [ONTOP — GitHub](https://github.com/ontop/ontop)
- [RMLMapper — GitHub](https://github.com/RMLio/rmlmapper-java)
- [Morph-KGC — GitHub](https://github.com/morph-kgc/morph-kgc)
- [SDM-RDFizer — GitHub](https://github.com/SDM-TIB/SDM-RDFizer)
- [W3C R2RML](https://www.w3.org/TR/r2rml/)
- [RML spec](https://rml.io/specs/rml/)
- [W3C CSVW](https://www.w3.org/TR/tabular-data-primer/)
- ADR-000 — ADR Process and Constraints
- ADR-001 — Triplestore and Semantic Stack Selection
