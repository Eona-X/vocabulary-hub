# Spike 1 — Oxigraph coverage matrix

**Gates:** L1/L2 swap (ADR-004 §1).

## What this spike answers

> For every capability the Vocabulary Hub is documented to need, does
> Oxigraph support it natively, support it with a companion component,
> or fail to support it at all?

ADR-004 phrases this as "enumerate which Jena features are actually
exercised in the current deployment." There is **no current deployment**.
The capability list is therefore derived from documented requirements:

| Source | What it specifies |
|---|---|
| `README.md` §Features | Turtle/JSON-LD/N-Triples/RDF-XML serializations; SPARQL endpoint; REST API |
| `docs/adr/001-triplestore-stack-selection.md` §Required capabilities | SPARQL 1.1 query + update + Graph Store Protocol + federation; drop-and-reload bulk load |
| `docs/adr/002-semantic-services-engine-selection.md` | SHACL Core + SHACL-SPARQL; OWL 2 RL (min) runtime inference; on-demand IRI dereferencing |
| IDS-RAM §3.5.6 Vocabulary Hub | SKOS-based concept schemes; vocabulary publication & lookup |
| W3C standards (README references) | RDF 1.1, OWL 2, SHACL, SKOS, SPARQL 1.1 |

The full enumeration lives in [`feature_matrix.md`](feature_matrix.md).
That is the spike's output document — `probe.py` populates the
machine-verifiable rows in it by exercising both engines.

## How it runs

`run.sh` does the following and writes everything to `results/<run-id>/`:

1. Boots a fresh Fuseki and a fresh oxigraph-server (via `../docker/`).
2. Loads `inputs/probe-dataset.ttl` into both (a tiny SKOS+OWL+SHACL
   fixture covering each feature row).
3. For each row in `feature_matrix.md` that has a `probe:` key, runs the
   recorded SPARQL query or HTTP request against both endpoints and
   records `pass / partial / fail` together with the raw response.
4. Rows that cannot be auto-probed (e.g. "runtime OWL 2 RL inference")
   are left as `manual` and link back to the documentation excerpt that
   justifies the verdict.
5. Writes:
   - `results/<run-id>/probe_results.json` — per-row machine output.
   - `results/<run-id>/raw/<row-id>/{fuseki,oxigraph}.{txt,json}` — raw
     responses, one file per probe per engine.
   - `results/<run-id>/feature_matrix.md` — rendered matrix with the
     verdict column filled in.
   - `results/<run-id>/summary.md` — pass/partial/fail counts +
     gating verdict.

The committed `feature_matrix.md` is the template; the per-run rendered
copy is the artifact reviewers cite.

## Why Jena/Fuseki is in the table

Not as an incumbent baseline — there isn't one — but as a known-complete
W3C reference. If a probe fails on **both** engines, the test itself is
likely wrong and the row is flagged for review rather than blamed on
Oxigraph.

## Re-running

```bash
docker compose -f ../docker/docker-compose.yml up -d
./run.sh
```
