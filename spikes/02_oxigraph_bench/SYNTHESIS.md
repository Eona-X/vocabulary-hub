# Spike 02 — Synthesis of L1/L2 bench results

Auto-generated from the latest run per (scale, framework) under `results/`. Regenerate with `python spikes/02_oxigraph_bench/harness/synthesize.py`.

Methodology: best-of-3 after a warmup; per-query timeout 300 s; row_count is the parsed `results.bindings` length (HTTP) or materialized iteration count (in-process). Peak RSS via psutil (in-process) or `docker stats` (Docker-backed).

## 100k

### Timing (best of 3, ms)

| Query | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| **load** | 219.8 | 829.8 | 727.5 | 3,960 | 3,426 | 1,089 | 1,000 |
| q1_count | 19.7 | 40.0 | 42.3 | 716.2 | 59.9 | 2.39 | 2.14 |
| q2_top_customers | 7.20 | 90.6 | 73.5 | 604.2 | 114.9 | 12.3 | 14.5 |
| q3_join_filter | 8.17 | 117.5 | 150.4 | 960.4 | 44.9 | 20.9 | 7.26 |
| q4_optional_agg | 10.7 | 65,813 | 97.9 | 207,925 | 123.3 | ERROR | 21.2 |

### Row count cross-check

| Query | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| q1_count ✅ | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| q2_top_customers ✅ | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| q3_join_filter ✅ | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| q4_optional_agg ✅ | 30 | 30 | 30 | 30 | 30 | — | 30 |

### p50 / p95 (ms)

| Query | maplib p50 | oxigraph p50 | oxigraph_fork p50 | rdflib p50 | fuseki_tdb2 p50 | qlever p50 | virtuoso p50 | maplib p95 | oxigraph p95 | oxigraph_fork p95 | rdflib p95 | fuseki_tdb2 p95 | qlever p95 | virtuoso p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q1_count | 20.6 | 40.1 | 42.8 | 717.4 | 78.4 | 2.58 | 2.48 | 20.6 | 40.1 | 42.9 | 740.6 | 102.1 | 3.22 | 3.88 |
| q2_top_customers | 7.59 | 92.5 | 91.1 | 611.6 | 116.3 | 13.4 | 16.1 | 7.59 | 131.1 | 128.2 | 613.1 | 224.2 | 14.5 | 18.8 |
| q3_join_filter | 8.53 | 119.4 | 181.5 | 967.7 | 45.4 | 24.5 | 7.38 | 8.68 | 132.8 | 220.9 | 976.3 | 49.8 | 25.5 | 7.80 |
| q4_optional_agg | 11.5 | 66,294 | 98.2 | 213,211 | 134.1 | — | 29.3 | 13.8 | 67,084 | 100.4 | 214,811 | 167.9 | — | 31.1 |

### Memory & storage

| Metric | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| peak RSS | 241.0 MiB | 142.0 MiB | 122.0 MiB | 345.1 MiB | 953.9 MiB | 50.9 MiB | 285.5 MiB |
| store on disk | — | 8.5 MiB | 8.5 MiB | — | 192.9 MiB | 13.7 MiB | 71.4 MiB |

### Notes

- **qlever q4_optional_agg**: `HTTP 500` — `{`

### Run provenance

| Framework | Run dir |
|---|---|
| maplib | `results/20260527T165758Z-728771b-d96159/raw/maplib/` |
| oxigraph | `results/20260527T165828Z-728771b-a044c1/raw/oxigraph/` |
| oxigraph_fork | `results/20260527T165759Z-728771b-dcc0ee/raw/oxigraph_fork/` |
| rdflib | `results/20260527T172024Z-728771b-ed8829/raw/rdflib/` |
| fuseki_tdb2 | `results/20260527T165818Z-728771b-194ff0/raw/fuseki_tdb2/` |
| qlever | `results/20260527T165803Z-728771b-ac6d9c/raw/qlever/` |
| virtuoso | `results/20260527T165808Z-728771b-09a767/raw/virtuoso/` |

## 1m

### Timing (best of 3, ms)

| Query | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| **load** | 2,347 | 5,695 | 5,323 | 36,200 | 8,291 | 2,605 | 4,807 |
| q1_count | 116.2 | 272.4 | 480.4 | 7,641 | 205.0 | 2.66 | 15.7 |
| q2_top_customers | 18.2 | 1,168 | 1,104 | 6,476 | 827.0 | 3.77 | 98.1 |
| q3_join_filter | 20.1 | 171.1 | 164.9 | 995.6 | 47.2 | 13.2 | 6.32 |
| q4_optional_agg | 28.4 | skipped | 1,721 | skipped | 1,089 | ERROR | 192.2 |

### Row count cross-check

| Query | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| q1_count ✅ | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| q2_top_customers ✅ | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| q3_join_filter ✅ | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| q4_optional_agg ✅ | 30 | — | 30 | — | 30 | — | 30 |

### p50 / p95 (ms)

| Query | maplib p50 | oxigraph p50 | oxigraph_fork p50 | rdflib p50 | fuseki_tdb2 p50 | qlever p50 | virtuoso p50 | maplib p95 | oxigraph p95 | oxigraph_fork p95 | rdflib p95 | fuseki_tdb2 p95 | qlever p95 | virtuoso p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q1_count | 117.0 | 289.6 | 544.8 | 7,684 | 336.3 | 2.85 | 16.3 | 117.2 | 294.1 | 583.3 | 9,043 | 390.1 | 2.98 | 19.8 |
| q2_top_customers | 18.5 | 1,182 | 1,269 | 6,801 | 845.0 | 4.90 | 98.6 | 20.7 | 1,193 | 1,286 | 8,832 | 897.1 | 5.42 | 100.2 |
| q3_join_filter | 20.4 | 173.5 | 165.5 | 1,124 | 48.1 | 13.4 | 7.52 | 20.8 | 174.9 | 166.2 | 1,181 | 59.5 | 13.9 | 8.43 |
| q4_optional_agg | 34.1 | — | 1,722 | — | 1,098 | — | 198.8 | 36.7 | — | 1,735 | — | 1,113 | — | 220.4 |

### Memory & storage

| Metric | maplib | oxigraph | oxigraph_fork | rdflib | fuseki_tdb2 | qlever | virtuoso |
|---|---|---|---|---|---|---|---|
| peak RSS | 912.5 MiB | 952.1 MiB | 957.8 MiB | 2.78 GiB | 1.08 GiB | 137.2 MiB | 647.8 MiB |
| store on disk | — | 144.3 MiB | 144.2 MiB | — | 336.8 MiB | 136.6 MiB | 211.8 MiB |

### Notes

- **oxigraph** skipped queries: q4_optional_agg (would not complete within budget at this scale).
- **rdflib** skipped queries: q4_optional_agg (would not complete within budget at this scale).
- **qlever q4_optional_agg**: `HTTP 500` — `{`

### Run provenance

| Framework | Run dir |
|---|---|
| maplib | `results/20260527T163039Z-728771b-f0207a/raw/maplib/` |
| oxigraph | `results/20260527T163634Z-728771b-753b34/raw/oxigraph/` |
| oxigraph_fork | `results/20260527T163101Z-728771b-94b8bb/raw/oxigraph_fork/` |
| rdflib | `results/20260527T163703Z-728771b-b1d133/raw/rdflib/` |
| fuseki_tdb2 | `results/20260527T163321Z-728771b-153524/raw/fuseki_tdb2/` |
| qlever | `results/20260527T163149Z-728771b-9b1a04/raw/qlever/` |
| virtuoso | `results/20260527T163215Z-728771b-bedbc6/raw/virtuoso/` |
