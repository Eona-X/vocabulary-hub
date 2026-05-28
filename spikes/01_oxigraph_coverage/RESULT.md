# Spike 1 result — Oxigraph coverage

**Verdict:** **PASS** — Oxigraph 0.5.8 clears the coverage gate.
18 of 20 auto-probed capabilities pass; the only remaining failure
(`sparql-service`) reproduces on Fuseki too and is network-bound, not
engine-bound.

- Run-id: [`20260521T183330Z-ae0a328-c4b749`](results/20260521T183330Z-ae0a328-c4b749/)
- Date: 2026-05-21
- Inputs kind: `public-reference` (no hub deployment exists)
- Engines: Oxigraph **0.5.8** (server, RocksDB backend) vs. Jena/Fuseki
  **5.1.0** (in-memory)
- Fixture: `inputs/probe-dataset.ttl` (SKOS + OWL + SHACL minimal graph)
  + `inputs/bulk-100k.nt` (100 000-triple deterministic SKOS taxonomy)

## Numbers

| engine   | pass | fail | manual | total |
|----------|-----:|-----:|-------:|------:|
| Oxigraph |   18 |    1 |      1 |    20 |
| Fuseki   |   18 |    1 |      1 |    20 |

Both engines fail only on `sparql-service` against `dbpedia.org`. The
test environment has no outbound network reachability for SPARQL
federation; the failure is not Oxigraph-specific. If/when the hub
requires federation in production, re-test with an internal reachable
SERVICE endpoint.

## What changed since the prior run

The previous run on **Oxigraph 0.4.7** reported two real gaps:

| Gap | Status on 0.4.7 | Status on 0.5.8 |
|---|---|---|
| **G1**: JSON-LD CONSTRUCT — `406 Not Acceptable` for `application/ld+json` | open (real coverage gap) | **closed** — Oxigraph now negotiates `application/ld+json` and returns valid JSON-LD |
| **G2**: SPARQL `SERVICE` federation — `400 Bad Request` | flagged | reproduces; **not engine-specific** — Fuseki also returns 400 in the sandbox |

The JSON-LD closure is the load-bearing change: G1 was the only gap
the L1/L2 swap had to engineer around. With it gone, the API-layer
JSON-LD transcoding workaround proposed in the prior RESULT.md is no
longer required.

Manual probe spot-check on the live endpoint:
```
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" \
    -H "Accept: application/ld+json" \
    --data-urlencode "query=CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 1" \
    http://localhost:7878/query
200 application/ld+json
```

## What Oxigraph passes (load-bearing rows)

SPARQL 1.1 SELECT / CONSTRUCT / ASK / DESCRIBE / UPDATE-INSERT /
UPDATE-DELETE; Graph Store Protocol PUT+GET; property paths; named
graphs; SKOS `broader+` transitive; **Turtle, JSON-LD, N-Triples,
RDF/XML, TriG content negotiation**; SPARQL-results JSON;
100k-triple bulk load.

## Rows not auto-probed (manual)

`C19 SHACL Core`, `C20 SHACL-SPARQL`, `C21 OWL 2 RL runtime inference`,
`C22 RDFS entailment regime`, `C23 Persistence restart`, `C25 HTTP
auth` — these belong to ADR-002 (companion components: `rudof`,
`reasonable`) or to deployment hardening, not to the L1/L2 engine
choice. Spike 1 does not block on them.

## Recommendation to ADR reviewer

Spike 1 is now a clean **PASS**. Combined with Spike 2's
deployment-realistic numbers (forthcoming RESULT.md update), the
evidence supports accepting the L1/L2 swap proposed by ADR-004.
The reviewer should:

1. Update ADR-004 §1 "gaps to verify" — JSON-LD is no longer a gap on
   Oxigraph 0.5+.
2. Decide whether SPARQL federation (SERVICE) is required by any
   documented hub use case; the working assumption is that it is not.
3. Pin the production deployment to **Oxigraph ≥ 0.5.8** (or whichever
   later release continues to ship JSON-LD).

## Reproducing

```bash
cd spikes
uv sync
docker compose -f docker/docker-compose.yml --profile tmpfs up -d
cd 01_oxigraph_coverage && ./run.sh
```

## Provenance

- `results/20260521T183330Z-ae0a328-c4b749/manifest.json` — git SHA,
  host, tool versions, sha256 of every input file.
- `…/probe_results.json` — 40 per-(row × engine) records.
- `…/raw/<probe>/<engine>.txt` — every HTTP response body.
- `…/feature_matrix.md` — rendered matrix.

Historical runs preserved alongside:

- `results/20260521T145859Z-728771b-c282e2/` — incomplete (Fuseki auth
  failure on data load; caught and fixed before re-run).
- `results/20260521T150143Z-728771b-c282e2/` — first complete run on
  Oxigraph 0.4.7 / Fuseki 5.0.0, where the JSON-LD gap was identified.
