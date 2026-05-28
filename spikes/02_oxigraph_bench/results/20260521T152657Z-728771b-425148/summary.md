# Spike 2 summary — 20260521T152657Z-728771b-425148

## Bulk load

| engine | triples | seconds | throughput (t/s) |
|---|---:|---:|---:|
| fuseki | 100000 | 0.58 | 171272 |
| oxigraph | 100000 | 3.42 | 29278 |

## Peak RSS (container PID + children)

| engine | peak RSS (MB) |
|---|---:|
| fuseki | 1253.8 |
| oxigraph | 452.4 |

## Query latency (ms)

| query | engine | p50 | p95 | p99 | mean |
|---|---|---:|---:|---:|---:|
| q01_label_lookup | fuseki | 42.5 | 60.3 | 85.6 | 44.0 |
| q02_broader_path | fuseki | 11.5 | 15.4 | 16.9 | 11.7 |
| q03_scheme_enum | fuseki | 21.8 | 27.6 | 28.9 | 21.4 |
| q04_construct_neighborhood | fuseki | 12.3 | 17.9 | 24.6 | 12.6 |
| q05_narrower_closure | fuseki | 42.3 | 50.6 | 66.7 | 41.6 |
| q06_named_graph | fuseki | 10.6 | 14.7 | 19.7 | 10.9 |
| q08_ask | fuseki | 9.6 | 12.2 | 16.3 | 9.9 |
| q07_update_insert | fuseki | 9.6 | 12.5 | 18.9 | 10.1 |
| q01_label_lookup | oxigraph | 70.1 | 93.3 | 102.7 | 73.5 |
| q02_broader_path | oxigraph | 2.2 | 2.4 | 2.4 | 2.2 |
| q03_scheme_enum | oxigraph | 21.6 | 32.3 | 38.6 | 23.1 |
| q04_construct_neighborhood | oxigraph | 2.4 | 2.7 | 2.8 | 2.4 |
| q05_narrower_closure | oxigraph | 67.5 | 82.0 | 89.4 | 66.4 |
| q06_named_graph | oxigraph | 46.0 | 65.8 | 74.4 | 46.0 |
| q08_ask | oxigraph | 2.1 | 2.4 | 2.5 | 2.1 |
| q07_update_insert | oxigraph | 2.1 | 2.6 | 2.9 | 2.1 |

**Note:** numbers are indicative until the hub team supplies a real
dataset and query mix; the manifest records `inputs.kind = public-reference`.