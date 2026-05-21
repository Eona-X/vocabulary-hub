# Spike 2 summary — 20260521T182913Z-ae0a328-425148

Variant: **disk** (deployment-realistic: Fuseki TDB2 on volume, Oxigraph RocksDB on volume)

## Bulk load

| engine | triples | seconds | throughput (t/s) |
|---|---:|---:|---:|
| fuseki | 100000 | 0.62 | 162200 |
| oxigraph | 100000 | 0.60 | 166966 |

## Peak RSS (container PID + children)

| engine | peak RSS (MB) |
|---|---:|
| fuseki | 1272.2 |
| oxigraph | 173.2 |

## Query latency (ms)

| query | engine | p50 | p95 | p99 | mean |
|---|---|---:|---:|---:|---:|
| q01_label_lookup | fuseki | 30.3 | 39.9 | 47.0 | 32.0 |
| q02_broader_path | fuseki | 5.2 | 7.7 | 9.3 | 5.5 |
| q03_scheme_enum | fuseki | 11.3 | 15.6 | 16.8 | 11.4 |
| q04_construct_neighborhood | fuseki | 4.8 | 7.3 | 9.2 | 5.2 |
| q05_narrower_closure | fuseki | 40.1 | 50.2 | 61.3 | 41.5 |
| q06_named_graph | fuseki | 4.5 | 6.4 | 7.1 | 4.8 |
| q08_ask | fuseki | 4.4 | 6.1 | 7.6 | 4.7 |
| q07_update_insert | fuseki | 45.3 | 50.6 | 63.8 | 46.1 |
| q01_label_lookup | oxigraph | 62.9 | 69.5 | 75.9 | 63.3 |
| q02_broader_path | oxigraph | 1.2 | 1.9 | 2.0 | 1.3 |
| q03_scheme_enum | oxigraph | 10.1 | 12.6 | 14.6 | 10.1 |
| q04_construct_neighborhood | oxigraph | 1.3 | 1.6 | 2.2 | 1.4 |
| q05_narrower_closure | oxigraph | 52.9 | 66.3 | 76.8 | 54.6 |
| q06_named_graph | oxigraph | 24.7 | 30.5 | 32.3 | 24.9 |
| q08_ask | oxigraph | 1.1 | 1.5 | 1.6 | 1.2 |
| q07_update_insert | oxigraph | 1.1 | 1.3 | 1.5 | 1.1 |

**Note:** numbers are indicative until the hub team supplies a real
dataset and query mix; the manifest records `inputs.kind = public-reference`.