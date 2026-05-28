"""
One-shot loader: fetch mobilityDCAT-AP RDF assets from GitHub and write them
into Oxigraph named graphs.

Idempotent: each asset is written with HTTP PUT on the Graph Store Protocol,
which replaces the target graph atomically. Re-running the container reloads
the same content into the same graphs without producing duplicate triples.
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
    source_path: str
    graph_iri: str
    content_type: str


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


def fetch(url: str) -> bytes:
    LOG.info("fetch %s", url)
    r = requests.get(url, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.content


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


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG.info("loader start: source=%s target=%s", SOURCE_BASE, OXIGRAPH_BASE)
    wait_for_oxigraph(OXIGRAPH_BASE, READY_TIMEOUT_S)

    for asset in ASSETS:
        body = fetch(f"{SOURCE_BASE}/{asset.source_path}")
        put_graph(OXIGRAPH_BASE, asset.graph_iri, asset.content_type, body)
        count = graph_size(OXIGRAPH_BASE, asset.graph_iri)
        LOG.info("graph %s now holds %d triples", asset.graph_iri, count)

    LOG.info("loader done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
