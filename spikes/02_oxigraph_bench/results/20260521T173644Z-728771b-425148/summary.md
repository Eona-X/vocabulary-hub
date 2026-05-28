# Spike 2 summary — 20260521T173644Z-728771b-425148

Variant: **tmpfs** (engine-only: Fuseki --mem, Oxigraph on tmpfs)

## Bulk load

| engine | triples | seconds | throughput (t/s) |
|---|---:|---:|---:|
| fuseki | 100000 | 0.86 | 116138 |
| oxigraph | 100000 | 3.06 | 32656 |

## Peak RSS (container PID + children)

| engine | peak RSS (MB) |
|---|---:|
| fuseki | 1175.9 |
| oxigraph | 243.3 |

## Query latency (ms)

| query | engine | p50 | p95 | p99 | mean |
|---|---|---:|---:|---:|---:|
| q01_label_lookup | fuseki | 48.2 | 84.4 | 91.6 | 51.2 |
| q02_broader_path | fuseki | 12.8 | 18.6 | 25.0 | 13.6 |
| q03_scheme_enum | fuseki | 21.7 | 27.4 | 28.0 | 21.7 |
| q04_construct_neighborhood | fuseki | 12.2 | 19.7 | 22.5 | 13.5 |
| q05_narrower_closure | fuseki | 37.2 | 48.5 | 50.2 | 37.7 |
| q06_named_graph | fuseki | 10.3 | 12.1 | 17.8 | 10.4 |
| q08_ask | fuseki | 9.7 | 13.3 | 15.4 | 10.1 |
| q07_update_insert | fuseki | 10.0 | 14.3 | 16.6 | 10.3 |
| q01_label_lookup | oxigraph | 58.2 | 71.4 | 74.4 | 59.9 |
| q02_broader_path | oxigraph | 2.2 | 2.7 | 2.9 | 2.2 |
| q03_scheme_enum | oxigraph | 13.0 | 16.5 | 17.3 | 13.0 |
| q04_construct_neighborhood | oxigraph | 2.4 | 2.8 | 3.3 | 2.5 |
| q05_narrower_closure | oxigraph | 48.6 | 52.7 | 55.1 | 48.3 |
| q06_named_graph | oxigraph | 30.1 | 36.6 | 37.2 | 29.0 |
| q08_ask | oxigraph | 2.1 | 2.4 | 2.6 | 2.1 |
| q07_update_insert | oxigraph | 2.1 | 2.6 | 2.6 | 2.1 |

**Note:** numbers are indicative until the hub team supplies a real
dataset and query mix; the manifest records `inputs.kind = public-reference`.