# Spike 2 summary — 20260521T182850Z-ae0a328-425148

Variant: **tmpfs** (engine-only: Fuseki --mem, Oxigraph on tmpfs)

## Bulk load

| engine | triples | seconds | throughput (t/s) |
|---|---:|---:|---:|
| fuseki | 100000 | 0.48 | 207844 |
| oxigraph | 100000 | 0.45 | 221147 |

## Peak RSS (container PID + children)

| engine | peak RSS (MB) |
|---|---:|
| fuseki | 1208.2 |
| oxigraph | 77.2 |

## Query latency (ms)

| query | engine | p50 | p95 | p99 | mean |
|---|---|---:|---:|---:|---:|
| q01_label_lookup | fuseki | 22.9 | 44.9 | 49.6 | 25.4 |
| q02_broader_path | fuseki | 6.0 | 9.0 | 9.6 | 6.2 |
| q03_scheme_enum | fuseki | 12.6 | 18.3 | 19.9 | 12.5 |
| q04_construct_neighborhood | fuseki | 4.6 | 6.6 | 7.7 | 4.9 |
| q05_narrower_closure | fuseki | 18.1 | 27.8 | 39.0 | 19.4 |
| q06_named_graph | fuseki | 4.3 | 8.7 | 9.2 | 4.8 |
| q08_ask | fuseki | 3.8 | 6.6 | 7.3 | 4.1 |
| q07_update_insert | fuseki | 4.1 | 8.6 | 9.2 | 4.8 |
| q01_label_lookup | oxigraph | 35.5 | 45.9 | 49.9 | 36.2 |
| q02_broader_path | oxigraph | 1.1 | 1.5 | 1.8 | 1.2 |
| q03_scheme_enum | oxigraph | 6.6 | 9.3 | 9.8 | 6.8 |
| q04_construct_neighborhood | oxigraph | 1.3 | 1.6 | 1.7 | 1.3 |
| q05_narrower_closure | oxigraph | 22.2 | 29.2 | 31.4 | 22.8 |
| q06_named_graph | oxigraph | 14.6 | 19.4 | 23.3 | 15.1 |
| q08_ask | oxigraph | 1.1 | 1.5 | 1.9 | 1.1 |
| q07_update_insert | oxigraph | 1.0 | 1.3 | 1.4 | 1.1 |

**Note:** numbers are indicative until the hub team supplies a real
dataset and query mix; the manifest records `inputs.kind = public-reference`.