"""
Integration tests for the L4 vocabulary browser (Prez over Oxigraph).

Each test fetches a live Prez response as Turtle, parses it with pyoxigraph, and
asserts via SPARQL — verifying the OGC Records hierarchy end to end:
catalog -> ConceptScheme collections -> Concept items (skos:inScheme).
"""

from __future__ import annotations

import pytest

from conftest import CATALOG, VOCAB_SCHEMES

SKOS = "http://www.w3.org/2004/02/skos/core#"
DCAT = "http://www.w3.org/ns/dcat#"
EONA_CATALOG_IRI = "https://vocab.eona-x.eu/catalog"


def _count(store, sparql: str) -> int:
    rows = list(store.query(sparql))
    return int(rows[0]["n"].value)


def _ask(store, sparql: str) -> bool:
    return bool(store.query(sparql))


def test_catalog_is_listed(fetch_store):
    """The Eona catalog appears in /catalogs as a dcat:Catalog."""
    store = fetch_store("/catalogs")
    assert _ask(
        store,
        f"ASK {{ <{EONA_CATALOG_IRI}> a <{DCAT}Catalog> }}",
    ), "eona:catalog not listed as dcat:Catalog at /catalogs"


def test_collections_lists_eleven_concept_schemes(fetch_store):
    """All 11 native vocabularies surface as ConceptScheme collections."""
    store = fetch_store(f"/catalogs/{CATALOG}/collections?limit=50")
    n = _count(
        store,
        f"SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a <{SKOS}ConceptScheme> }}",
    )
    assert n == len(VOCAB_SCHEMES), f"expected 11 ConceptScheme collections, got {n}"


@pytest.mark.parametrize("scheme", VOCAB_SCHEMES)
def test_scheme_items_have_concepts(fetch_store, scheme):
    """Each ConceptScheme's /items lists at least one skos:Concept."""
    store = fetch_store(f"/catalogs/{CATALOG}/collections/{scheme}/items?limit=500")
    n = _count(
        store,
        f"SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{ ?c a <{SKOS}Concept> }}",
    )
    assert n > 0, f"{scheme}/items returned no concepts"


def test_transport_mode_known_concepts(fetch_store):
    """transport-mode exposes its full concept list with expected members."""
    store = fetch_store(
        f"/catalogs/{CATALOG}/collections/mob:transport-mode/items?limit=500"
    )
    n = _count(
        store,
        f"SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{ ?c a <{SKOS}Concept> }}",
    )
    assert n >= 24, f"transport-mode expected >=24 concepts, got {n}"
    for slug in ("air", "bus", "metro-subway-train"):
        iri = f"https://w3id.org/mobilitydcat-ap/transport-mode/{slug}"
        assert _ask(
            store, f"ASK {{ <{iri}> a <{SKOS}Concept> }}"
        ), f"transport-mode missing concept {slug}"


def test_total_concepts_across_schemes(fetch_store):
    """Sanity floor on the whole vocabulary corpus served by Prez."""
    total = 0
    for scheme in VOCAB_SCHEMES:
        store = fetch_store(
            f"/catalogs/{CATALOG}/collections/{scheme}/items?limit=500"
        )
        total += _count(
            store,
            f"SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{ ?c a <{SKOS}Concept> }}",
        )
    assert total >= 200, f"expected >=200 concepts across schemes, got {total}"
