# Oxigraph 0.5.8 — OPTIONAL with multi-pattern group exhibits super-linear scaling

**Status:** Reproducible.
**Severity:** Blocks adoption for any workload that uses `OPTIONAL { ?o a Foo ; p ?x ; q ?y }` against a non-trivial dataset.
**Found while:** validating ADR-004's L1/L2 component re-selection against Apache Jena Fuseki (see `spikes/02_oxigraph_bench/`).
**Engine:** Oxigraph 0.5.x (via pyoxigraph 0.5.8 — `pip show pyoxigraph`).
**Comparison engine:** Apache Jena Fuseki 5.2.0 / TDB2 — same query, same data, **~500× faster** at 100k triples.

## Summary

Queries of the shape

```sparql
SELECT ... (COUNT(...) AS ?n) (SUM(...) AS ?r)
WHERE {
  ?lhs <type> <T> ;
       <p1> ?a ;
       <p2> ?b .
  OPTIONAL {
    ?rhs <type> <U> ;
         <fk> ?lhs ;
         <v>  ?metric .
  }
}
GROUP BY ?a ?b
```

scale **super-linearly** (≈ quadratic in the LHS×RHS join cardinality) on Oxigraph 0.5.8. Removing the `OPTIONAL` and using an inner join restores linear scaling and matches the performance of mature SPARQL engines.

The pathology is the **OPTIONAL itself**, not `GROUP BY`, `SUM`, `COALESCE`, or `ORDER BY` — variants without the aggregate and without the group still scale super-linearly as long as the multi-triple OPTIONAL pattern remains.

## Environment

| Component | Version |
|---|---|
| pyoxigraph | 0.5.8 |
| Oxigraph engine | (bundled with pyoxigraph 0.5.8) |
| Python | 3.12.3 |
| OS | Linux 6.8.0-117-generic x86_64 |
| Store | `Store(path=...)` (disk-backed RocksDB), fresh, bulk-loaded once |
| Comparator | Apache Jena Fuseki 5.2.0, TDB2 backend (`tdb2.tdbloader --loader=phased`) |

## Dataset

Deterministic synthetic e-commerce graph. Seeded with `random.Random(42)`.

| Scale | Customers | Products | Orders | N-Triples | Total triples |
|---|---:|---:|---:|---:|---:|
| **small** | 200 | 500 | 1,400 | 750 KB | ~11,000 |
| **100k** | 2,000 | 5,000 | 14,000 | 7.6 MB | ~114,000 |

Schema (only the parts that matter for Q1/V1..V5):

```
ex:customer/i  rdf:type           schema:Person .
ex:customer/i  schema:addressCountry "FR"|...
ex:customer/i  ex:segment         "retail"|"smb"|"enterprise"
ex:order/j     rdf:type           schema:Order .
ex:order/j     schema:customer    ex:customer/k .
ex:order/j     schema:totalPrice  "..."^^xsd:decimal .
```

The reproducer (`repro.py`) regenerates this from scratch, no external assets.

## Reproducer

```bash
pip install pyoxigraph==0.5.8
python repro.py --scale small    # ~3s total runtime
python repro.py --scale 100k     # ~3min total (V1/V3/V4 each take ~60s)
```

`repro.py` is in this directory.

## Observed timings

Each cell is wall-clock for a single execution from a fresh `Store.bulk_load`-ed disk store. Each query returns the same 28–30 result rows. No warmup. Best of one (we are characterising the slowdown, not micro-optimising).

| Variant | What changed vs. V1 | small (1.4K orders) | 100k (14K orders) | Scaling factor (10×data) |
|---|---|---:|---:|---:|
| **V1** original | — | 855 ms | **61,224 ms** | 72× |
| **V2** no OPTIONAL | OPTIONAL → required pattern | 9 ms | 92 ms | **9.8×** (linear) |
| **V3** no GROUP BY | dropped `GROUP BY`, raw rows | 753 ms | 68,963 ms | 92× |
| **V4** no SUM, COUNT only | removed `SUM(?total)` | 718 ms | 62,008 ms | 86× |
| **V5** UNION + FILTER NOT EXISTS | OPTIONAL rewritten as UNION | 213 ms | 15,165 ms | 71× |

Reference point: Apache Jena Fuseki / TDB2 5.2.0 on the **same data**, **same V1 query**:

| Metric | Oxigraph 0.5.8 | Fuseki+TDB2 5.2.0 |
|---|---:|---:|
| V1 at 100k (best of 3) | 63.5 s | **128 ms** |
| Ratio | — | **~500×** |

## Diagnosis

Data scaled exactly 10× from "small" → "100k" (10× customers, 10× orders). V2 grew 9.8× — that's linear, as expected for the inner join over a hashed index. V1/V3/V4 grew 72–92× — that is the **product of the LHS and RHS cardinalities growing**, which is the signature of a **nested-loop OPTIONAL** that does not use an index on the join key (`schema:customer`).

V5 (rewriting `OPTIONAL { ... }` as `{ ... } UNION { FILTER NOT EXISTS { ... } BIND(0 AS ?total) }`) still has the same shape (~71×) because the `FILTER NOT EXISTS` subquery is itself executed per row.

Counts of result rows are identical across all variants (V1=V2=V4=V5=30; V3=14,002 because of no aggregation). **This is a performance issue, not a correctness issue.**

The likely root cause is the optimiser choosing — or being unable to recognise — that the OPTIONAL group can be evaluated as a hash-join on `?customer` with a probe side built from the orders triple pattern. Expected behaviour: linear in `|orders| + |customers|`, matching V2.

A useful next step (outside the scope of this report) is to obtain Oxigraph's chosen plan for V1, V3, and V5 via whatever explain/trace facility the engine exposes, and confirm whether the OPTIONAL operator binds to a SeqScan-then-FilterRight rather than to a HashJoin.

## Why this matters for downstream users

`OPTIONAL` is fundamental to SPARQL: it is how RDF expresses the equivalent of a SQL `LEFT JOIN`. Any analytical query of the form "all entities, with their related metric if any" uses it. The Q4 shape in our benchmark is intentionally generic — `OPTIONAL { ?related a Class ; <fk> ?lhs ; <metric> ?v }` — and the regression appears at modest scales (~14K right-hand-side rows). Vocabulary-hub workloads in particular hit this shape frequently when summarising terms by usage.

A 500× regression vs. Apache Jena at 14K orders implies the gap widens further at 100K+ orders, and **at our adoption-decision scale (1M+ triples) this query is effectively non-executable** unless rewritten manually. Manual rewrite of every analytical query is not an option for a project that intends to expose a general SPARQL endpoint.

## References

- W3C SPARQL 1.1 Query — §10 *OPTIONAL*: <https://www.w3.org/TR/sparql11-query/#optionals>
- W3C SPARQL 1.1 Query — §18.5 *Evaluation Semantics* (LeftJoin): <https://www.w3.org/TR/sparql11-query/#sparqlAlgebraEval>
- Oxigraph repository: <https://github.com/oxigraph/oxigraph>
- Oxigraph issues: <https://github.com/oxigraph/oxigraph/issues>
- pyoxigraph 0.5.8: <https://pypi.org/project/pyoxigraph/0.5.8/>
- Apache Jena Fuseki 5.2.0 (comparator): <https://jena.apache.org/download/>
- Comparable shape in standard benchmarks: BSBM Q5 (OPTIONAL + aggregation): <http://wbsg.informatik.uni-mannheim.de/bizer/berlinsparqlbenchmark/>
- Bench harness this finding came from: `spikes/02_oxigraph_bench/` in this repo
- ADR that triggered the investigation: `docs/adr/004-l1-l3-component-reselection.md` §1 (L1/L2 — Oxigraph vs. Jena/Fuseki)

## Files in this directory

- `repro.py` — single-file, dependency-free reproducer. Generates data, loads, runs V1–V5, prints timings.
- `README.md` — this document.
- `upstream_issue_draft.md` — ready-to-paste GitHub issue text for `oxigraph/oxigraph`.
- `fork_comparison.md` — **fix verification**: Deepthought-Solutions/oxigraph fork (commit `5c7feb9`) eliminates the pathology. V1: 61.2 s → 267 ms.

## Suggested upstream issue title

> OPTIONAL with multi-pattern group scales quadratically with join cardinality (0.5.8)
