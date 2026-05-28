<!--
Ready to paste into https://github.com/oxigraph/oxigraph/issues/new
Title suggestion (use the "Title" field, not in the body):
  OPTIONAL with multi-pattern group scales quadratically with join cardinality (0.5.8)
-->

## Summary

Queries containing an `OPTIONAL` whose group has more than one triple pattern over a foreign-key shape scale **super-linearly** (≈ quadratic in `|LHS| × |RHS|`) on Oxigraph 0.5.8. Replacing the `OPTIONAL` with a required (inner) join restores linear scaling. The same query on Apache Jena Fuseki 5.2.0 (TDB2) is ~500× faster at 100K triples on the same data.

This looks like a planner / cost-model issue: the optimiser does not appear to use the index on the join key inside the OPTIONAL right-hand side; the result rows are correct in all variants, so it is a performance, not a correctness, problem.

## Environment

| Component | Version |
|---|---|
| pyoxigraph | 0.5.8 (`pip install pyoxigraph==0.5.8`) |
| Python | 3.12.3 |
| OS | Linux 6.8.0 x86_64 |
| Store | `Store(path=...)` — disk-backed RocksDB |

## Reproducer (single file, ~120 lines, no external deps)

```python
# repro.py
import argparse, gc, random, shutil, tempfile, time
from pathlib import Path
from pyoxigraph import RdfFormat, Store

EX, SCHEMA, XSD, RDF = (
    "http://example.org/", "http://schema.org/",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
)
COUNTRIES = ["FR","DE","ES","IT","NL","BE","PT","PL","SE","NO"]
SEGMENTS  = ["retail","smb","enterprise"]

def gen_nt(n_c, n_p, n_o, seed=42):
    rng = random.Random(seed); L = []
    for i in range(n_c):
        u = f"<{EX}customer/{i}>"
        L += [f'{u} <{RDF}type> <{SCHEMA}Person> .',
              f'{u} <{SCHEMA}addressCountry> "{rng.choice(COUNTRIES)}" .',
              f'{u} <{EX}segment> "{rng.choice(SEGMENTS)}" .']
    for i in range(n_p):
        L.append(f'<{EX}product/{i}> <{RDF}type> <{SCHEMA}Product> .')
    for i in range(n_o):
        u = f"<{EX}order/{i}>"
        c = f"<{EX}customer/{rng.randrange(n_c)}>"
        total = round(rng.uniform(5.0, 2000.0), 2)
        L += [f'{u} <{RDF}type> <{SCHEMA}Order> .',
              f'{u} <{SCHEMA}customer> {c} .',
              f'{u} <{SCHEMA}totalPrice> "{total:.2f}"^^<{XSD}decimal> .']
    return "\n".join(L) + "\n"

V1 = """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?n) (COALESCE(SUM(?total),0) AS ?r)
WHERE {
  ?c a schema:Person ;
     schema:addressCountry ?country ;
     ex:segment ?segment .
  OPTIONAL {
    ?order a schema:Order ;
           schema:customer ?c ;
           schema:totalPrice ?total .
  }
} GROUP BY ?country ?segment
"""

V2 = """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?n) (SUM(?total) AS ?r)
WHERE {
  ?c a schema:Person ;
     schema:addressCountry ?country ;
     ex:segment ?segment .
  ?order a schema:Order ;
         schema:customer ?c ;
         schema:totalPrice ?total .
} GROUP BY ?country ?segment
"""

def time_q(store, q):
    gc.collect(); t = time.perf_counter()
    n = sum(1 for _ in store.query(q))
    return time.perf_counter() - t, n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=["small","100k"], default="small")
    args = ap.parse_args()
    n_c, n_p, n_o = (200, 500, 1_400) if args.scale == "small" else (2_000, 5_000, 14_000)
    work = Path(tempfile.mkdtemp(prefix="ox-repro-"))
    try:
        nt = work / "data.nt"; nt.write_text(gen_nt(n_c, n_p, n_o))
        s = Store(path=str(work / "store"))
        s.bulk_load(path=str(nt), format=RdfFormat.N_TRIPLES)
        for tag, q in (("V1 OPTIONAL", V1), ("V2 inner join", V2)):
            dt, n = time_q(s, q)
            print(f"{tag:18s}  rows={n:>4d}  time={dt*1000:7.1f} ms")
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
```

Run with:

```bash
python repro.py --scale small      # ~1s total
python repro.py --scale 100k       # ~1min — V1 takes ~60s
```

## Observed timings

Each cell is a single execution on a fresh `bulk_load`-ed disk store. Result row counts are identical across V1 and V2 (30 rows = country × segment combinations).

| Variant | small (1.4K orders) | 100k (14K orders) | Scaling factor (10×data) |
|---|---:|---:|---:|
| **V1** OPTIONAL + GROUP BY + SUM | 855 ms | **61,224 ms** | **72×** |
| **V2** OPTIONAL → required pattern | 9 ms | 92 ms | 9.8× *(linear)* |

Data grew exactly 10× (10× customers, 10× orders). V2 grew 10×. V1 grew 72×. The signature is `|LHS| × |RHS|` — a nested-loop over the OPTIONAL group.

Two further variants confirm the GROUP BY and SUM are not implicated (full table in [the linked investigation](#)):

| Variant | small | 100k |
|---|---:|---:|
| OPTIONAL only, no GROUP BY (raw rows) | 753 ms | 68,963 ms |
| OPTIONAL + GROUP BY, no SUM (COUNT only) | 718 ms | 62,008 ms |
| OPTIONAL rewritten as `{ ... } UNION { FILTER NOT EXISTS { ... } BIND(0 AS ?total) }` | 213 ms | 15,165 ms |

Comparator on the identical 100k dataset and V1 query, with Apache Jena Fuseki 5.2.0 / TDB2 (loaded with `tdb2.tdbloader --loader=phased`):

| Engine | V1 at 100k |
|---|---:|
| Oxigraph 0.5.8 | 63.5 s |
| Fuseki 5.2.0 / TDB2 | **128 ms** |

## Expected behaviour

OPTIONAL over a foreign-key shape should be planned as a hash-/merge-join keyed on `?c`, giving `O(|customers| + |orders|)`. The chosen plan appears to instead probe the orders pattern for each row of the LHS, giving `O(|customers| × |orders|)`. This is consistent with V2 (which is the same join expressed without OPTIONAL) executing in ~92 ms at 100k.

## Why this matters

`OPTIONAL` is the SPARQL equivalent of SQL `LEFT JOIN` and is fundamental to analytical queries of the shape "all entities, with their related metric if any". The pattern in V1 is intentionally generic. A 500× gap against Jena at 14K right-hand-side rows widens further at larger scales; at ~1M triples the query is effectively non-executable without manual rewrite to V2 (which is not always possible — V2 drops customers who have no orders, V1 keeps them).

## Possibly related

I did not find an open issue with this specific shape; happy to be pointed at one and close this if it duplicates. A pointer to whatever explain/trace facility exposes the chosen plan for V1 would also be useful — I would gladly attach that output if it helps.

## A fix already exists in a public fork

The Deepthought-Solutions fork (<https://github.com/Deepthought-Solutions/oxigraph>) ships a one-file patch at commit `5c7feb9` titled *"bugfix/optimizer: fix quadratic scaling of OPTIONAL in a JOIN on FK"*. It modifies `lib/sparopt/src/optimizer.rs` only: the `LeftJoin` handler now reorders the right side into a `Lateral( left, LeftJoin(EmptySingleton, right, ..., HashBuildRightProbeLeft) )` when the OPTIONAL group is fit-for-for-loop-join and shares variables with the LHS; a small cost-model nudge doubles the size estimate for `?s rdf:type <T>` triple patterns; and the patch ships a regression test whose query is V1 verbatim.

I built that branch from source and re-ran the same reproducer on the same data: V1 drops from 61.2 s to **267 ms** at 100k, V3 from 69 s to 250 ms, V4 from 62 s to 67 ms. V2 (the inner-join control) stays at the same low-hundred-ms range. So the fix is real, focused, tested, and would be a natural upstream PR if the maintainer agrees with the approach.

(Happy to convert this into a PR review thread if that's more useful than an issue.)

## Steps to verify a fix

Re-run `python repro.py --scale 100k`. The expected acceptance criterion is V1 within roughly 2–3× of V2 (i.e. low-hundreds of milliseconds at 100k), matching the algorithmic complexity of the join.

---

*Found while benchmarking L1/L2 triplestore candidates for an open-source Vocabulary Hub project. Full investigation, including additional variants and dataset characterisation, is at `spikes/02_oxigraph_bench/investigations/q4_oxigraph_optional/` in the bench repo.*
