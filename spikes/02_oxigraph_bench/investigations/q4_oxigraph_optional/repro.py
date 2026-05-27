"""Minimal reproducer for the Q4 OPTIONAL+GROUP BY slowdown in Oxigraph 0.5.8.

Background: on a ~114K-triple synthetic e-commerce dataset (2,000 customers,
5,000 products, 14,000 orders), this query takes ~63s in Oxigraph 0.5.8 vs.
~128ms in Apache Jena Fuseki 5.2.0 (TDB2).

Variants below isolate which clause is the cause:
  V1: original Q4 (OPTIONAL + GROUP BY + COALESCE + SUM)
  V2: drop OPTIONAL  (inner join only)
  V3: drop GROUP BY  (OPTIONAL only, raw rows)
  V4: drop SUM, keep COUNT
  V5: rewrite OPTIONAL as MINUS / UNION

Run with: python repro.py [--scale 100k|small]

The 'small' scale uses 200 customers / 500 products / 1,400 orders (1/10th)
to characterise how the slowdown scales.
"""
from __future__ import annotations

import argparse
import gc
import random
import shutil
import tempfile
import time
from pathlib import Path

from pyoxigraph import RdfFormat, Store

EX = "http://example.org/"
SCHEMA = "http://schema.org/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

COUNTRIES = ["FR", "DE", "ES", "IT", "NL", "BE", "PT", "PL", "SE", "NO"]
SEGMENTS = ["retail", "smb", "enterprise"]
CATEGORIES = ["books", "music", "video", "electronics", "kitchen", "garden", "toys", "sports"]


def gen_nt(n_c: int, n_p: int, n_o: int, seed: int = 42) -> str:
    rng = random.Random(seed)
    lines: list[str] = []
    for i in range(n_c):
        u = f"<{EX}customer/{i}>"
        lines += [
            f'{u} <{RDF}type> <{SCHEMA}Person> .',
            f'{u} <{SCHEMA}name> "Customer {i}" .',
            f'{u} <{SCHEMA}addressCountry> "{rng.choice(COUNTRIES)}" .',
            f'{u} <{EX}segment> "{rng.choice(SEGMENTS)}" .',
        ]
    for i in range(n_p):
        u = f"<{EX}product/{i}>"
        lines += [
            f'{u} <{RDF}type> <{SCHEMA}Product> .',
            f'{u} <{SCHEMA}category> "{rng.choice(CATEGORIES)}" .',
        ]
    for i in range(n_o):
        u = f"<{EX}order/{i}>"
        c = f"<{EX}customer/{rng.randrange(n_c)}>"
        p = f"<{EX}product/{rng.randrange(n_p)}>"
        total = round(rng.uniform(5.0, 2000.0), 2)
        lines += [
            f'{u} <{RDF}type> <{SCHEMA}Order> .',
            f'{u} <{SCHEMA}customer> {c} .',
            f'{u} <{SCHEMA}orderedItem> {p} .',
            f'{u} <{SCHEMA}totalPrice> "{total:.2f}"^^<{XSD}decimal> .',
        ]
    return "\n".join(lines) + "\n"


QUERIES: dict[str, str] = {
    "V1_original": """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?orders) (COALESCE(SUM(?total), 0) AS ?revenue)
WHERE {
  ?customer a schema:Person ;
            schema:addressCountry ?country ;
            ex:segment ?segment .
  OPTIONAL {
    ?order a schema:Order ;
           schema:customer ?customer ;
           schema:totalPrice ?total .
  }
}
GROUP BY ?country ?segment
ORDER BY ?country ?segment
""",
    "V2_no_optional": """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?orders) (SUM(?total) AS ?revenue)
WHERE {
  ?customer a schema:Person ;
            schema:addressCountry ?country ;
            ex:segment ?segment .
  ?order a schema:Order ;
         schema:customer ?customer ;
         schema:totalPrice ?total .
}
GROUP BY ?country ?segment
ORDER BY ?country ?segment
""",
    "V3_no_groupby": """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?customer ?country ?segment ?order ?total
WHERE {
  ?customer a schema:Person ;
            schema:addressCountry ?country ;
            ex:segment ?segment .
  OPTIONAL {
    ?order a schema:Order ;
           schema:customer ?customer ;
           schema:totalPrice ?total .
  }
}
""",
    "V4_count_only": """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?orders)
WHERE {
  ?customer a schema:Person ;
            schema:addressCountry ?country ;
            ex:segment ?segment .
  OPTIONAL {
    ?order a schema:Order ;
           schema:customer ?customer .
  }
}
GROUP BY ?country ?segment
""",
    "V5_union_rewrite": """
PREFIX schema: <http://schema.org/>
PREFIX ex: <http://example.org/>
SELECT ?country ?segment (COUNT(?order) AS ?orders) (SUM(?total) AS ?revenue)
WHERE {
  ?customer a schema:Person ;
            schema:addressCountry ?country ;
            ex:segment ?segment .
  {
    ?order a schema:Order ;
           schema:customer ?customer ;
           schema:totalPrice ?total .
  } UNION {
    FILTER NOT EXISTS {
      ?o a schema:Order ; schema:customer ?customer .
    }
    BIND(0 AS ?total)
  }
}
GROUP BY ?country ?segment
""",
}


def time_query(store: Store, q: str, timeout_s: float) -> tuple[float, int]:
    gc.collect()
    t0 = time.perf_counter()
    n = 0
    try:
        for _ in store.query(q):
            n += 1
            if time.perf_counter() - t0 > timeout_s:
                return float("inf"), n
    except Exception as e:
        return -1.0, -1
    return time.perf_counter() - t0, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=["small", "100k"], default="small")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    if args.scale == "small":
        n_c, n_p, n_o = 200, 500, 1_400
    else:
        n_c, n_p, n_o = 2_000, 5_000, 14_000

    print(f"# scale=small  customers={n_c}  products={n_p}  orders={n_o}")
    work = Path(tempfile.mkdtemp(prefix="ox-q4-repro-"))
    try:
        nt = work / "data.nt"
        nt.write_text(gen_nt(n_c, n_p, n_o))
        print(f"# nt_bytes={nt.stat().st_size}")

        store = Store(path=str(work / "store"))
        t0 = time.perf_counter()
        store.bulk_load(path=str(nt), format=RdfFormat.N_TRIPLES)
        print(f"# load_s={time.perf_counter() - t0:.3f}")

        for name, q in QUERIES.items():
            dt, n = time_query(store, q, timeout_s=args.timeout)
            tag = "TIMEOUT" if dt == float("inf") else (f"{dt*1000:.1f} ms" if dt >= 0 else "ERROR")
            print(f"  {name:20s}  rows={n:>6d}  time={tag}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
