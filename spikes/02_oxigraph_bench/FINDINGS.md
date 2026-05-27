# Spike 02 — Findings

Curated interpretation of the bench results. Raw numbers live in
[SYNTHESIS.md](SYNTHESIS.md); reproduction recipes and per-engine adapter notes
live in [README.md](README.md).

## Headline

| Question | Answer (at 1M triples) |
|---|---|
| Do all engines return the same rows for Q1–Q4? | **Yes**, where they complete: 1 / 20 / 100 / 30. The bench is internally consistent. |
| Is stock Oxigraph 0.5.8 a viable Jena/Fuseki replacement? | **No.** Q4 is unusable (would not complete within 300 s; quadratic OPTIONAL plan), see [`investigations/q4_oxigraph_optional/`](investigations/q4_oxigraph_optional/). |
| Does the Deepthought fork fix it? | **Yes.** Q4 at 1M completes in 1.7 s — competitive with Fuseki (1.1 s) and Virtuoso (192 ms). All other queries unchanged. |
| Is there a single "fastest"? | **No.** Different engines win different shapes. See per-query table below. |
| Which engines crash or refuse a query? | QLever crashes on Q4 (`Assertion 'singleResult.size() == 1' failed`); rdflib and stock Oxigraph are skipped on Q4 at 1M for runtime reasons. |

## Per-query winner at 1M (best of 3, ms)

| Query | Winner | Runner-up | Note |
|---|---|---|---|
| Q1 count | **QLever 2.7 ms** | Virtuoso 15.7 ms | QLever is ~6× faster than the next non-server engine and ~75× faster than Fuseki. |
| Q2 top-20 agg | **QLever 3.8 ms** | maplib 18.2 ms | Same shape — QLever's group-by path is the fastest where it doesn't hit Q4's bug. |
| Q3 3-way join + filter | **Virtuoso 6.3 ms** | QLever 13.2 ms | Mature SQL planner shows; Fuseki at 47 ms also competitive. |
| Q4 OPTIONAL + agg | **maplib 28.4 ms** | Virtuoso 192 ms | maplib's Polars-Arrow execution is dramatically faster on this shape; Oxigraph fork (1.7 s) and Fuseki (1.1 s) are the realistic high-end among mature SPARQL engines. |
| load (1M triples) | **maplib 2.3 s** | QLever 2.6 s | Both in the 2–3 s band. rdflib (36 s) is an outlier. |

## Memory & storage at 1M

| Engine | Peak RSS | Store on disk | Notes |
|---|---:|---:|---|
| **QLever** | 137 MiB* | 137 MiB | Lowest on both axes. *RSS via `docker stats`, may underreport slightly. |
| **Virtuoso** | 648 MiB | 212 MiB | Disciplined server. |
| **maplib** | 913 MiB | — | In-memory full materialization. |
| **oxigraph (stock & fork)** | 952–958 MiB | 144 MiB | Disk store is small; RSS reflects working set. |
| **Fuseki + TDB2** | 1.08 GiB | 337 MiB | JVM + 4 GiB heap allocated. |
| **rdflib** | 2.78 GiB | — | Pure-Python overhead. |

## Q4 status across engines (the bench's diagnostic query)

| Engine | At 100k | At 1M | Verdict |
|---|---|---|---|
| maplib | 11 ms | 28 ms | Linear; Polars execution. |
| oxigraph 0.5.8 (stock) | 65.8 s | skipped | **Quadratic OPTIONAL pathology**; see investigation. |
| oxigraph fork @ 5c7feb9 | 98 ms | 1.72 s | **Fixed** by the Deepthought patch. |
| rdflib | 208 s | skipped | Pure Python; not a Q4-specific issue. |
| Fuseki + TDB2 | 123 ms | 1.09 s | Healthy. |
| QLever | **HTTP 500** (assertion) | **HTTP 500** (assertion) | **Engine bug**: `GroupByImpl.cpp:442` `singleResult.size() == 1` fails on `COALESCE(SUM(?total), 0)` with OPTIONAL. Independent of the Oxigraph finding. |
| Virtuoso | 21 ms | 192 ms | Healthy. |

## Implications for ADR-004

1. **§1 L1/L2 — Oxigraph vs. Jena/Fuseki.** Stock Oxigraph fails the perf gate on the OPTIONAL pattern (Q4). The Deepthought fork passes. Adoption path is either upstream the patch or vendor the fork — both viable.
2. **Coverage matters.** QLever is the fastest on Q1–Q3 but the Q4 crash means it cannot be a drop-in for a general SPARQL endpoint without filing and getting that fixed. Virtuoso and Fuseki+TDB2 are the only mature OSS engines that handle all four queries without incident.
3. **maplib's promise holds on this workload.** For the L1 in-memory role at the hub's scale, it is the fastest engine on every query that completes correctly. Its SPARQL coverage at the broader W3C test-suite level still needs the ADR-004 spike to clear.
4. **rdflib is a documentation/baseline, not a production candidate.** The 10–100× gap to the next engine, combined with 2.8 GiB RSS at 1M, rules it out for any serving role — which matches the existing ADR posture.

## Known caveats

- **QLever RSS via `docker stats`** is a coarser measurement than the psutil-based sampler used for in-process engines; treat the 137 MiB figure as a lower-bound order-of-magnitude.
- **Single-machine, single-run "best of 3"**: not a statistically rigorous benchmark. The deltas highlighted here are large enough (often >10×) to survive that limitation; per-query p50/p95 are in [SYNTHESIS.md](SYNTHESIS.md) for the cases where variance matters.
- **Synthetic e-commerce schema** (matches trainmarks). Vocabulary-hub workloads will exercise different shapes (OWL/SKOS reasoning, SHACL validation, `SERVICE` federation). These are coverage spikes still owed under ADR-004 §1.
- **rdflib and stock-Oxigraph Q4 at 1M were skipped, not measured.** Both would have exceeded the 300 s budget by a large margin; the skip is the result, not absence of data.

## Open follow-ups

- [ ] File the upstream Oxigraph Q4 issue (draft ready in [`investigations/q4_oxigraph_optional/upstream_issue_draft.md`](investigations/q4_oxigraph_optional/upstream_issue_draft.md)); link the Deepthought fork commit as a candidate fix.
- [ ] File a QLever Q4 issue against `ad-freiburg/qlever` (writeup not yet drafted).
- [ ] Add RDF4J Native, TerminusDB, HDT adapters — still on the matrix in the README.
- [ ] Coverage spike: enumerate the Jena features the hub actually exercises and check each against Oxigraph / Virtuoso / QLever (§1 of ADR-004).
- [ ] Re-run at 10M scale once the QLever Q4 and Oxigraph Q4 issues land; the 10M run is the one ADR-004 should ultimately cite.
