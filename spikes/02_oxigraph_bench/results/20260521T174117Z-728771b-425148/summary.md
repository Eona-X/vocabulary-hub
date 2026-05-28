# Spike 2 summary — 20260521T174117Z-728771b-425148

Variant: **disk** (deployment-realistic: Fuseki TDB2 on volume, Oxigraph RocksDB on volume)

## Bulk load

| engine | triples | seconds | throughput (t/s) |
|---|---:|---:|---:|
| fuseki | 100000 | 2.15 | 46538 |
| oxigraph | 100000 | 2.95 | 33847 |

## Peak RSS (container PID + children)

| engine | peak RSS (MB) |
|---|---:|
| fuseki | 1252.5 |
| oxigraph | 243.4 |

## Query latency (ms)

| query | engine | p50 | p95 | p99 | mean |
|---|---|---:|---:|---:|---:|
| q01_label_lookup | fuseki | 61.0 | 76.7 | 94.5 | 61.9 |
| q02_broader_path | fuseki | 13.5 | 16.7 | 19.4 | 13.3 |
| q03_scheme_enum | fuseki | 25.0 | 34.5 | 38.0 | 25.7 |
| q04_construct_neighborhood | fuseki | 12.1 | 15.4 | 18.2 | 12.2 |
| q05_narrower_closure | fuseki | 66.8 | 92.7 | 116.9 | 69.8 |
| q06_named_graph | fuseki | 11.1 | 19.1 | 20.7 | 11.9 |
| q08_ask | fuseki | 10.1 | 13.3 | 21.1 | 10.5 |
| q07_update_insert | fuseki | 84.3 | 91.2 | 93.4 | 84.5 |
| q01_label_lookup | oxigraph | 62.0 | 69.2 | 70.0 | 60.6 |
| q02_broader_path | oxigraph | 2.1 | 2.5 | 2.6 | 2.2 |
| q03_scheme_enum | oxigraph | 11.1 | 13.2 | 16.9 | 11.2 |
| q04_construct_neighborhood | oxigraph | 2.4 | 2.9 | 3.2 | 2.5 |
| q05_narrower_closure | oxigraph | 44.8 | 54.4 | 55.6 | 45.5 |
| q06_named_graph | oxigraph | 29.6 | 35.3 | 38.4 | 28.7 |
| q08_ask | oxigraph | 2.1 | 2.5 | 2.5 | 2.2 |
| q07_update_insert | oxigraph | 2.1 | 2.5 | 2.7 | 2.1 |

**Note:** numbers are indicative until the hub team supplies a real
dataset and query mix; the manifest records `inputs.kind = public-reference`.