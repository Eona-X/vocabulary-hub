# Spike 1 inputs

- `probe-dataset.ttl` — minimal SKOS + OWL + SHACL fixture; loaded into
  both engines before the probe sweep so every row has something to
  query against.
- `probe-graph.ttl` — single-triple graph used by the GSP PUT/GET probe.
- `bulk-100k.nt` — 100 000-triple synthetic SKOS expansion, generated
  deterministically by `gen_bulk.py`. **Not committed** (~12 MB);
  `run.sh` regenerates it, and its sha256 in `manifest.json` pins the
  exact bytes that produced any given run.
