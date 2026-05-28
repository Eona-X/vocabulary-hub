"""
One-shot loader: fetch mobilityDCAT-AP RDF assets from GitHub and write them
into Oxigraph named graphs, then rebuild the default graph as the union of
those named graphs.

Why mirror to default: Prez 4.x queries the SPARQL default graph for its OGC
Records endpoints. Data sitting only in named graphs is invisible to Prez.

Idempotency: each asset is written with HTTP PUT on the Graph Store Protocol
(atomic replace of the target graph). The default-graph rebuild drops the
default graph and re-inserts the union — also idempotent. Re-running the
container reloads identical content without producing duplicate triples.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from urllib.parse import quote

import requests

LOG = logging.getLogger("loader")

OXIGRAPH_BASE = os.environ.get("OXIGRAPH_BASE", "http://oxigraph:7878")
SOURCE_BASE = os.environ.get(
    "SOURCE_BASE",
    "https://raw.githubusercontent.com/Eona-X/mobilityDCAT-AP/HEAD",
)
READY_TIMEOUT_S = int(os.environ.get("READY_TIMEOUT_S", "120"))
HTTP_TIMEOUT_S = int(os.environ.get("HTTP_TIMEOUT_S", "60"))


@dataclass(frozen=True)
class Asset:
    # source resolution:
    #   local=True     -> source_path is a filesystem path (vs the script dir)
    #   absolute=True  -> source_path is a full URL fetched as-is
    #   otherwise      -> source_path is relative to SOURCE_BASE
    source_path: str
    graph_iri: str
    content_type: str
    local: bool = False
    absolute: bool = False


# mobilityDCAT-AP native controlled vocabularies. Each w3id IRI content-negotiates
# (303) to its published SKOS/Turtle on GitHub Pages. The scheme IRI doubles as the
# named-graph IRI so a scheme's skos:Concepts (skos:inScheme <scheme>) land in the
# same graph as their skos:ConceptScheme — this is what lets Prez list concepts as
# OGC Records `items` under each scheme-as-collection.
_VOCAB_SLUGS: tuple[str, ...] = (
    "application-layer-protocol",
    "communication-method",
    "conditions-for-access-and-usage",
    "georeferencing-method",
    "grammar",
    "intended-information-service",
    "mobility-data-standard",
    "mobility-theme",
    "network-coverage",
    "transport-mode",
    "update-frequency",
)


def _vocab_assets() -> tuple[Asset, ...]:
    return tuple(
        Asset(
            source_path=f"https://w3id.org/mobilitydcat-ap/{slug}",
            graph_iri=f"https://w3id.org/mobilitydcat-ap/{slug}",
            content_type="text/turtle",
            absolute=True,
        )
        for slug in _VOCAB_SLUGS
    )


ASSETS: tuple[Asset, ...] = (
    Asset(
        source_path="drafts/latest/mobilitydcat-ap.ttl",
        graph_iri="https://w3id.org/mobilitydcat-ap",
        content_type="text/turtle",
    ),
    Asset(
        source_path="drafts/latest/shaclShapes/mobilitydcat-ap-shacl.ttl",
        graph_iri="https://w3id.org/mobilitydcat-ap/shacl",
        content_type="text/turtle",
    ),
    Asset(
        source_path="drafts/latest/shaclShapes/mobilitydcat-ap-shacl-ranges.ttl",
        graph_iri="https://w3id.org/mobilitydcat-ap/shacl-ranges",
        content_type="text/turtle",
    ),
    *_vocab_assets(),
    # Catalog wrapper: declares a dcat:Catalog whose dcterms:hasPart members are the
    # graphs above (ontology + SHACL as resource pages, each vocabulary as a
    # browsable skos:ConceptScheme) so Prez can list/route them via OGC Records.
    Asset(
        source_path="catalog.ttl",
        graph_iri="https://vocab.eona-x.eu/catalog",
        content_type="text/turtle",
        local=True,
    ),
)


def wait_for_oxigraph(base: str, timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base}/", timeout=5)
            if r.status_code < 500:
                LOG.info("oxigraph reachable at %s (status=%d)", base, r.status_code)
                return
        except requests.RequestException as e:
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"oxigraph not ready after {timeout_s}s: {last_err}")


def fetch(url: str, accept: str = "text/turtle") -> bytes:
    LOG.info("fetch %s", url)
    # Accept header drives w3id.org content negotiation toward the Turtle
    # serialisation; redirects (303 -> GitHub Pages) are followed by default.
    r = requests.get(url, headers={"Accept": accept}, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.content


def read_local(path: str) -> bytes:
    full = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    LOG.info("read %s", full)
    with open(full, "rb") as fh:
        return fh.read()


def put_graph(base: str, graph_iri: str, content_type: str, body: bytes) -> None:
    url = f"{base}/store?graph={quote(graph_iri, safe='')}"
    LOG.info("PUT %d bytes -> %s", len(body), url)
    r = requests.put(
        url,
        data=body,
        headers={"Content-Type": content_type},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"PUT {url} failed: {r.status_code} {r.text[:500]}"
        )
    LOG.info("graph %s loaded (status=%d)", graph_iri, r.status_code)


def graph_size(base: str, graph_iri: str) -> int:
    q = f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}"
    r = requests.get(
        f"{base}/query",
        params={"query": q},
        headers={"Accept": "application/sparql-results+json"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return int(r.json()["results"]["bindings"][0]["n"]["value"])


def default_graph_size(base: str) -> int:
    q = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
    r = requests.get(
        f"{base}/query",
        params={"query": q},
        headers={"Accept": "application/sparql-results+json"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return int(r.json()["results"]["bindings"][0]["n"]["value"])


def sparql_update(base: str, update: str) -> None:
    r = requests.post(
        f"{base}/update",
        data={"update": update},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(
            f"SPARQL UPDATE failed: {r.status_code} {r.text[:500]}"
        )


def rebuild_default_graph(base: str, graph_iris: tuple[str, ...]) -> None:
    """
    Drop the default graph, then copy every named graph's contents into it.
    Idempotent: re-running yields the same union.
    """
    LOG.info("rebuilding default graph as union of %d named graphs", len(graph_iris))
    sparql_update(base, "DROP SILENT DEFAULT")
    for iri in graph_iris:
        sparql_update(base, f"INSERT {{ ?s ?p ?o }} WHERE {{ GRAPH <{iri}> {{ ?s ?p ?o }} }}")


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG.info("loader start: source=%s target=%s", SOURCE_BASE, OXIGRAPH_BASE)
    wait_for_oxigraph(OXIGRAPH_BASE, READY_TIMEOUT_S)

    for asset in ASSETS:
        if asset.local:
            body = read_local(asset.source_path)
        elif asset.absolute:
            body = fetch(asset.source_path, accept=asset.content_type)
        else:
            body = fetch(f"{SOURCE_BASE}/{asset.source_path}")
        put_graph(OXIGRAPH_BASE, asset.graph_iri, asset.content_type, body)
        count = graph_size(OXIGRAPH_BASE, asset.graph_iri)
        LOG.info("graph %s now holds %d triples", asset.graph_iri, count)

    rebuild_default_graph(OXIGRAPH_BASE, tuple(a.graph_iri for a in ASSETS))
    LOG.info("default graph now holds %d triples", default_graph_size(OXIGRAPH_BASE))

    LOG.info("loader done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
