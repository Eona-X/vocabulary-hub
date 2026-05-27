"""Deterministic synthetic e-commerce dataset generator.

Mirrors the trainmarks data shape (customers, products, orders) so query results
are comparable. Re-implemented from scratch (trainmarks has no license).

Emits N-Triples (.nt) directly and a Turtle (.ttl) variant with prefix block.
Both contain identical triples.

Scales:
  100k   ~100,000 triples
  1m     ~1,000,000 triples
  10m   ~10,000,000 triples
"""
from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

EX = "http://example.org/"
EX_C = EX + "customer/"
EX_P = EX + "product/"
EX_O = EX + "order/"
SCHEMA = "http://schema.org/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

COUNTRIES = ["FR", "DE", "ES", "IT", "NL", "BE", "PT", "PL", "SE", "NO"]
SEGMENTS = ["retail", "smb", "enterprise"]
CATEGORIES = ["books", "music", "video", "electronics", "kitchen", "garden", "toys", "sports"]

# tuning: customers + products + orders chosen so the triple count lands near target
SCALES = {
    "100k":  {"customers":  2_000, "products":  5_000, "orders":  14_000},
    "1m":    {"customers": 20_000, "products": 50_000, "orders": 140_000},
    "10m":   {"customers": 200_000, "products": 500_000, "orders": 1_400_000},
}


def _iri(s: str) -> str:
    return f"<{s}>"


def _lit(v: str, dt: str | None = None) -> str:
    # NT literal: escape backslash and double-quote
    esc = v.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{esc}\"" + (f"^^<{dt}>" if dt else "")


def _emit_nt(s: str, p: str, o: str) -> str:
    return f"{s} {p} {o} .\n"


def generate(scale: str, out_dir: Path, seed: int = 42) -> dict[str, int]:
    cfg = SCALES[scale]
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    nt_path = out_dir / f"data-{scale}.nt"
    ttl_path = out_dir / f"data-{scale}.ttl"

    triples = 0

    with nt_path.open("w") as nt, ttl_path.open("w") as ttl:
        ttl.write(
            "@prefix ex: <http://example.org/> .\n"
            "@prefix schema: <http://schema.org/> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n\n"
        )

        # ---- customers ----
        for i in range(cfg["customers"]):
            uri = _iri(f"{EX_C}{i}")
            country = rng.choice(COUNTRIES)
            segment = rng.choice(SEGMENTS)
            for line in (
                _emit_nt(uri, _iri(RDF + "type"), _iri(SCHEMA + "Person")),
                _emit_nt(uri, _iri(SCHEMA + "name"), _lit(f"Customer {i}")),
                _emit_nt(uri, _iri(SCHEMA + "email"), _lit(f"c{i}@example.org")),
                _emit_nt(uri, _iri(SCHEMA + "addressCountry"), _lit(country)),
                _emit_nt(uri, _iri(EX + "segment"), _lit(segment)),
            ):
                nt.write(line)
                ttl.write(line)
                triples += 1

        # ---- products ----
        for i in range(cfg["products"]):
            uri = _iri(f"{EX_P}{i}")
            cat = rng.choice(CATEGORIES)
            price = round(rng.uniform(1.0, 500.0), 2)
            for line in (
                _emit_nt(uri, _iri(RDF + "type"), _iri(SCHEMA + "Product")),
                _emit_nt(uri, _iri(SCHEMA + "name"), _lit(f"Product {i}")),
                _emit_nt(uri, _iri(SCHEMA + "category"), _lit(cat)),
                _emit_nt(uri, _iri(SCHEMA + "price"), _lit(f"{price:.2f}", XSD + "decimal")),
            ):
                nt.write(line)
                ttl.write(line)
                triples += 1

        # ---- orders ----
        base_date = date(2025, 1, 1)
        n_c, n_p = cfg["customers"], cfg["products"]
        for i in range(cfg["orders"]):
            uri = _iri(f"{EX_O}{i}")
            cust = _iri(f"{EX_C}{rng.randrange(n_c)}")
            prod = _iri(f"{EX_P}{rng.randrange(n_p)}")
            qty = rng.randint(1, 10)
            total = round(rng.uniform(5.0, 2000.0), 2)
            d = base_date + timedelta(days=rng.randint(0, 364))
            for line in (
                _emit_nt(uri, _iri(RDF + "type"), _iri(SCHEMA + "Order")),
                _emit_nt(uri, _iri(SCHEMA + "customer"), cust),
                _emit_nt(uri, _iri(SCHEMA + "orderedItem"), prod),
                _emit_nt(uri, _iri(SCHEMA + "orderQuantity"), _lit(str(qty), XSD + "integer")),
                _emit_nt(uri, _iri(SCHEMA + "totalPrice"), _lit(f"{total:.2f}", XSD + "decimal")),
                _emit_nt(uri, _iri(SCHEMA + "orderDate"), _lit(d.isoformat(), XSD + "date")),
            ):
                nt.write(line)
                ttl.write(line)
                triples += 1

    return {
        "scale": scale,
        "triples": triples,
        "nt_bytes": nt_path.stat().st_size,
        "ttl_bytes": ttl_path.stat().st_size,
        "nt_path": str(nt_path),
        "ttl_path": str(ttl_path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=list(SCALES), default="100k")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    info = generate(args.scale, args.out, args.seed)
    print(info)


if __name__ == "__main__":
    main()
