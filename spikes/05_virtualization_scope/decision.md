# Virtualization scope decision (ADR-004 §3)

> Decision owner: **TBD (product owner)**
> Status: **Open**
> Decision required before: ADR-004 can move from Proposed → Accepted

## Question

Does the Vocabulary Hub need **general SQL virtualization** (arbitrary
relational sources exposed as RDF via SPARQL-to-SQL rewriting) or only
**time-series / analytical joins** against a knowledge graph?

This decides whether Chrontext is a candidate at all:

| Scope answer | Outcome |
|---|---|
| General SQL virtualization needed | **Keep ONTOP.** Chrontext does not cover this case. Close ADR-004 §3. |
| Time-series-only virtualization | Evaluate Chrontext through the same coverage / maturity / RSS / perf gate as Spikes 1–4. |
| No virtualization at all | Drop ONTOP from the stack. Close ADR-004 §3 with "L3 virtualization not required". |

## Evidence to weigh

- IDS-RAM §3.5.6 describes the Vocabulary Hub as a publication/lookup
  service for ontologies, schemas, and reference data — it does **not**
  mandate virtualization over external relational sources.
- ADR-002 references runtime IRI dereferencing with on-demand inference;
  that is **not** SQL virtualization, and is served by Jena/Oxigraph +
  a reasoner, not by ONTOP/Chrontext.
- ADR-001 §Required capabilities does not list relational source
  federation.
- The hub is greenfield; nothing in the repository today depends on
  relational sources being exposed as RDF.

## Working hypothesis (until product-owner override)

**No virtualization required.** Rationale: the documented hub
requirements describe a vocabulary publication service over native RDF
storage, with reasoning and SHACL applied to that storage. Relational
virtualization appears nowhere in the requirements set. Until the
product owner identifies a concrete use case that needs it, ADR-004 §3
should close as "L3 virtualization not required; both ONTOP and
Chrontext out of scope."

If this hypothesis stands, ADR-003 (mapping & virtualization) should be
revised to drop the virtualization half.

## TBD (product owner)

1. Is there a stakeholder use case that requires querying a relational
   data source as if it were RDF, through the hub?
2. If yes — is the source a time-series store (Chrontext applicable) or
   a general SQL database (ONTOP required)?
3. What is the freshness requirement? (Materialised RML output via L3
   ETL may obviate virtualization if hours-old data is acceptable.)

## Decision

_Awaiting product-owner input. Update this section and re-run
`./record.sh` to commit a new dated snapshot._
