"""Generate a deterministic synthetic N-Triples bulk-load fixture.

Usage:  python gen_bulk.py [N]    (default N=100000)
Output: N-Triples on stdout, byte-stable across runs given the same N.

The shape mimics what a Vocabulary Hub would actually store: SKOS
concepts in a synthetic taxonomy with prefLabel, broader links, and
inScheme assertions. Public-reference scale, no real-world data.
"""

from __future__ import annotations

import sys

NS = "https://eona.example/bulk/"
SCHEME = NS + "scheme"


def emit(n: int) -> None:
    out = sys.stdout.write
    out(f"<{SCHEME}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
        f"<http://www.w3.org/2004/02/skos/core#ConceptScheme> .\n")
    # Aim for ~5 triples per concept ⇒ ceil(n/5) concepts.
    concepts = (n + 4) // 5
    written = 1
    for i in range(concepts):
        if written >= n:
            break
        c = f"{NS}c{i}"
        triples = [
            (c, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
             "http://www.w3.org/2004/02/skos/core#Concept"),
            (c, "http://www.w3.org/2004/02/skos/core#inScheme", SCHEME),
            (c, "http://www.w3.org/2004/02/skos/core#prefLabel",
             f'"concept-{i}"@en'),
        ]
        if i > 0:
            parent = f"{NS}c{i // 5}"
            triples.append(
                (c, "http://www.w3.org/2004/02/skos/core#broader", parent)
            )
        # one extra definition triple
        triples.append(
            (c, "http://www.w3.org/2004/02/skos/core#definition",
             f'"synthetic concept #{i}"@en')
        )
        for s, p, o in triples:
            if written >= n:
                return
            if o.startswith('"'):
                out(f"<{s}> <{p}> {o} .\n")
            else:
                out(f"<{s}> <{p}> <{o}> .\n")
            written += 1


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    emit(n)
