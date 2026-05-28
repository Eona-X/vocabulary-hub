"""
Shared fixtures for the vocabulary-browser integration tests.

The tests treat Prez as a black box: fetch RDF over HTTP with content
negotiation, parse it into an in-memory pyoxigraph Store, and assert with
SPARQL. Using pyoxigraph here mirrors the runtime stack — Oxigraph 0.5.8 backs
the triplestore and Prez itself parses into a pyoxigraph store — so the query
semantics under test match production exactly.
"""

from __future__ import annotations

import os
import time

import pytest
import requests
from pyoxigraph import RdfFormat, Store

PREZ_BASE = os.environ.get("PREZ_BASE", "http://prez:8000").rstrip("/")
READY_TIMEOUT_S = int(os.environ.get("READY_TIMEOUT_S", "120"))
HTTP_TIMEOUT_S = int(os.environ.get("HTTP_TIMEOUT_S", "30"))

# Eona Vocabulary Hub catalog, addressed by the curie Prez registers from the
# vann prefix binding in catalog.ttl.
CATALOG = "eona:catalog"

# mobilityDCAT-AP native controlled vocabularies, by Prez curie (mob: prefix).
# Mirrors load.py's _VOCAB_SLUGS — these are the schemes that must be browsable.
VOCAB_SCHEMES: tuple[str, ...] = (
    "mob:application-layer-protocol",
    "mob:communication-method",
    "mob:conditions-for-access-and-usage",
    "mob:georeferencing-method",
    "mob:grammar",
    "mob:intended-information-service",
    "mob:mobility-data-standard",
    "mob:mobility-theme",
    "mob:network-coverage",
    "mob:transport-mode",
    "mob:update-frequency",
)


@pytest.fixture(scope="session", autouse=True)
def _wait_for_prez() -> None:
    """Block until Prez answers 200 on /catalogs (link generation done)."""
    deadline = time.monotonic() + READY_TIMEOUT_S
    last = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{PREZ_BASE}/catalogs", timeout=5)
            if r.status_code == 200:
                return
            last = f"status={r.status_code}"
        except requests.RequestException as e:  # not up yet
            last = repr(e)
        time.sleep(2)
    pytest.fail(f"Prez not ready at {PREZ_BASE} after {READY_TIMEOUT_S}s ({last})")


def _fetch_store(path: str) -> Store:
    """GET a Prez endpoint as Turtle and load it into a fresh pyoxigraph Store."""
    url = f"{PREZ_BASE}{path}"
    r = requests.get(url, headers={"Accept": "text/turtle"}, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    store = Store()
    store.load(r.content, format=RdfFormat.TURTLE)
    return store


@pytest.fixture(scope="session")
def fetch_store():
    """Factory: path -> pyoxigraph Store of the parsed Turtle response."""
    return _fetch_store
