# Vocabulary Hub feature matrix — Oxigraph vs. Jena/Fuseki

Source-of-truth template. `probe.py` reads this file, runs each row's
`probe:` block against both engines, and writes a rendered copy with the
verdict columns filled in to `results/<run-id>/feature_matrix.md`.

Verdict legend: `pass` / `partial` / `fail` / `manual` / `n-a`.

| # | Capability | Source | Probe | Oxigraph | Fuseki | Notes |
|---|---|---|---|---|---|---|
| C01 | SPARQL 1.1 SELECT | ADR-001 | `probe: sparql-select` | pass | n-a | basic conjunctive |
| C02 | SPARQL 1.1 CONSTRUCT | ADR-001 | `probe: sparql-construct` | pass | n-a | |
| C03 | SPARQL 1.1 ASK | ADR-001 | `probe: sparql-ask` | pass | n-a | |
| C04 | SPARQL 1.1 DESCRIBE | ADR-001 | `probe: sparql-describe` | pass | n-a | |
| C05 | SPARQL 1.1 UPDATE — INSERT DATA | ADR-001 | `probe: sparql-update-insert` | pass | n-a | |
| C06 | SPARQL 1.1 UPDATE — DELETE WHERE | ADR-001 | `probe: sparql-update-delete` | pass | n-a | |
| C07 | SPARQL 1.1 Graph Store Protocol | ADR-001 | `probe: gsp-put-get` | pass | n-a | |
| C08 | SPARQL 1.1 Federation (SERVICE) | ADR-001 | `probe: sparql-service` | fail | n-a | ADR-004 flagged as gap-to-verify |
| C09 | Property paths | SPARQL 1.1 | `probe: sparql-paths` | pass | n-a | |
| C10 | Named graphs / quads | RDF 1.1 | `probe: named-graphs` | pass | n-a | |
| C11 | Turtle parse + serialize | README | `probe: io-turtle` | pass | n-a | |
| C12 | JSON-LD parse + serialize | README | `probe: io-jsonld` | fail | n-a | |
| C13 | N-Triples parse + serialize | README | `probe: io-ntriples` | pass | n-a | |
| C14 | RDF/XML parse + serialize | README | `probe: io-rdfxml` | pass | n-a | |
| C15 | TriG / N-Quads | RDF 1.1 | `probe: io-trig` | pass | n-a | bulk-load formats listed in ADR-004 §1 |
| C16 | Content negotiation on SPARQL endpoint | README | `probe: conneg` | pass | n-a | |
| C17 | SKOS concept-scheme query (skos:broader transitive) | IDS-RAM §3.5.6 | `probe: skos-broader` | pass | n-a | |
| C18 | Full-text index | ADR-004 §1 gap | `probe: text-search` | pass | n-a | ADR-004 calls out as gap-to-verify |
| C19 | SHACL Core validation | ADR-002 | `manual` | _tbd_ | _tbd_ | not built into Oxigraph; companion: rudof |
| C20 | SHACL-SPARQL validation | ADR-002 | `manual` | _tbd_ | _tbd_ | Jena yes; Oxigraph no |
| C21 | OWL 2 RL runtime inference | ADR-002 | `manual` | _tbd_ | _tbd_ | Oxigraph: none built-in; companion: reasonable |
| C22 | RDFS entailment regime in SPARQL | ADR-002 | `manual` | _tbd_ | _tbd_ | |
| C23 | Persistent on-disk store | ADR-001 | `probe: persistence-restart` | manual | n-a | Oxigraph: RocksDB |
| C24 | Bulk load (≥ 1M triples) | ADR-004 §1 | `probe: bulk-load` | pass | n-a | timed separately in Spike 2 |
| C25 | HTTP auth (admin / read-only) | ADR-001 hub deployment | `manual` | _tbd_ | _tbd_ | reverse-proxy fronting in both cases |

## Probe specifications

Each `probe:` key resolves to a block in `probes.yaml` (committed). A
probe block names the HTTP method, endpoint, headers, body / SPARQL
string, and the verdict rule (`pass-if`: `status==200 and rows>0`,
`bindings-contain`, etc.). Keeping probes in YAML rather than Python
makes the matrix reviewable in a single diff.

## Verdict rules

- A row is `fail` if Oxigraph returns an error, a 4xx/5xx, or a result
  that violates `pass-if`.
- A row is `partial` if it returns a 2xx but with a documented caveat
  (e.g. SERVICE works but only over GET, no UPDATE).
- `manual` rows are filled in by a human reviewer pointing at upstream
  documentation; the rendered copy in `results/<run-id>/feature_matrix.md`
  embeds the citation URL.

## Gating rule

The spike **passes** when every row in {C01–C17, C23, C24} is `pass` on
Oxigraph. C18–C22 and C25 can be `manual` or `n-a` provided the linked
companion component is named and the operational impact is recorded in
the per-run `summary.md`.