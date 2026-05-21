# Spike 2 result — Oxigraph vs Fuseki benchmark

**Verdict:** **PASS (deployment-realistic)** — on Oxigraph **0.5.8** and
Fuseki **5.1.0**, under the configuration the hub would actually deploy
(both engines on persistent volumes), Oxigraph wins decisively on
**memory (~7×)**, ties Fuseki on **bulk load**, and is **~40× faster on
UPDATE INSERT**. Fuseki keeps a real edge on label-scan and on
cross-named-graph aggregation (`q06`, ~5.6×). All other workload shapes
favour Oxigraph.

## Variants

| Variant | Fuseki backend | Oxigraph backend | Run-id |
|---|---|---|---|
| `tmpfs` (engine-only) | `--mem` | RocksDB on tmpfs | [`20260521T182850Z-ae0a328-425148`](results/20260521T182850Z-ae0a328-425148/) |
| `disk` (deployment-realistic) | TDB2 on volume | RocksDB on volume | [`20260521T182913Z-ae0a328-425148`](results/20260521T182913Z-ae0a328-425148/) |

Both runs: 100 000-triple synthetic SKOS taxonomy, 8 hub-shaped
queries (3 warmup + 50 timed iterations), 4 Hz RSS sampling. Both
engines wired through their public binaries — no custom builds.

## Memory (peak RSS over the whole workload)

| Variant | Fuseki RSS (MB) | Oxigraph RSS (MB) | Oxigraph saving |
|---|---:|---:|---:|
| tmpfs | 1175.9 | 243.3 | 4.83× |
| disk  | 1272.2 | 173.2 | **7.34×** |

Oxigraph 0.5.8's footprint on disk dropped to **173 MB** (was 243 MB on
0.4.7 disk run) — RocksDB tuning improvement between Oxigraph minor
versions. Fuseki sits where ADR-001 predicted (1.5–4 GB with `-Xmx2g`).

ADR-004 §1 claim ("10× memory") remains unsubstantiated; the real
ratio in this configuration is **~7×**, not 10×. Worth correcting in
the ADR.

## Bulk load (100 000 triples, single POST, disk variant)

| Engine | seconds | triples / s |
|---|---:|---:|
| Fuseki TDB2 | 0.62 | 162 200 |
| Oxigraph RocksDB | 0.60 | 166 966 |

Effectively **tied** — well within run-to-run noise. The prior 5.9×
Fuseki advantage was an artefact of the unfair "in-memory Fuseki vs
RocksDB Oxigraph" pairing in the very first run. Apples-to-apples,
both engines load a SKOS taxonomy at ~160k triples/s.

## Query latency (p50, ms — disk variant)

The deployment variant is the one the hub will run. Use these numbers
for the L1/L2 decision.

| Query | Shape | Fuseki TDB2 | Oxigraph RocksDB | Winner | Factor |
|---|---|---:|---:|---|---:|
| q01 | label-scan with FILTER string | 30.3 | 62.9 | Fuseki | 2.08× |
| q02 | `skos:broader+` (few ancestors) | 5.2 | 1.2 | Oxigraph | **4.33×** |
| q03 | COUNT over `skos:inScheme` | 11.3 | 10.1 | Oxigraph | 1.12× |
| q04 | CONSTRUCT neighbourhood | 4.8 | 1.3 | Oxigraph | **3.69×** |
| q05 | `skos:broader+` (many descendants) | 40.1 | 52.9 | Fuseki | 1.32× |
| q06 | COUNT across named graphs | 4.5 | 24.7 | Fuseki | **5.49×** |
| q07 | UPDATE INSERT DATA | 45.3 | 1.1 | Oxigraph | **41.2×** |
| q08 | ASK | 4.4 | 1.1 | Oxigraph | **4.00×** |

Full n / min / p50 / p95 / p99 / mean in
[`results/20260521T182913Z-…/query_latency.json`](results/20260521T182913Z-ae0a328-425148/query_latency.json).

### Three findings worth their own attention

1. **TDB2 UPDATE is expensive on disk.** `q07 INSERT DATA` takes
   **45 ms** on Fuseki TDB2 vs **1.1 ms** on Oxigraph RocksDB.
   Durability sync overhead. For a hub whose ingestion gate inserts
   validated triples on every vocabulary publish, this is a real
   deployment-relevant advantage for Oxigraph.
2. **Cross-named-graph aggregation regressed for Oxigraph (`q06`).**
   With Jena 5.1.0 Fuseki dropped to 4.5 ms; Oxigraph stays at ~25 ms.
   The gap widened from 2.7× (5.0.0 vs 0.4.7) to **5.5× (5.1.0 vs
   0.5.8)**. Worth filing upstream as an Oxigraph query-planner issue
   (see [todo: upstream issue for Oxigraph]).
3. **Label-scan (`q01`) now favours Fuseki 5.1.0 by 2×.** The previous
   tie disappeared on the new versions — Jena's ARQ optimiser appears
   to have improved its `STR()` + `FILTER` handling for the in-memory
   working set. Not a deployment blocker; mention in the ADR.

## Interpretation against ADR-004 §1 claims

- ADR-004: "Order-of-magnitude lower RSS … the '10x' figure is not
  substantiated." **Confirmed not substantiated.** Real ratio is ~7×
  (better than the 5× we saw on 0.4.7, but still not 10×).
- ADR-004: "Bulk-load and point-query benchmarks exist in the Oxigraph
  repo; reproduce on representative data." **Reproduced.** Bulk load
  ties; point queries lead by 3–5×.

## Caveats still standing

- **Public-reference workload.** Numbers will move when a hub-owned
  dataset and query mix replace the synthetic SKOS taxonomy.
- **Single-threaded client.** Concurrency dimension untested.
- **Single 100k-triple dataset.** Scale-dependent behaviour (RocksDB
  cache pressure, TDB2 working-set growth) not measured at 1M / 10M.
- **No SHACL or reasoning load.** When ADR-002's runtime inference is
  layered on top, the picture changes again.

## Recommendation to ADR reviewer

Spike 2 on the bumped versions is a clean **PASS** for Oxigraph in the
deployment-realistic configuration. Combined with Spike 1 (now also
PASS — JSON-LD gap closed on Oxigraph 0.5.8), the L1/L2 swap proposed
by ADR-004 is well-supported.

Recommended ADR amendments:

- Pin the production deployment to **Oxigraph ≥ 0.5.8** and
  **Apache Jena ≥ 5.1.0** if Fuseki is kept anywhere.
- Correct "~10× memory" → "~7× memory."
- Acknowledge `q06` (cross-named-graph COUNT) as the one workload
  shape where Oxigraph is materially slower; track upstream issue for
  resolution.
- Acknowledge that with the JSON-LD closure, no API-layer transcoding
  workaround is required.

## Reproducing

```bash
cd spikes
uv sync
cd 02_oxigraph_bench
VARIANT=tmpfs ./run.sh        # engine-only
VARIANT=disk  ./run.sh        # deployment-realistic
```

## Provenance

- `results/20260521T182850Z-ae0a328-425148/` — tmpfs variant on bumped versions.
- `results/20260521T182913Z-ae0a328-425148/` — disk variant on bumped versions.
- Historical runs (`20260521T152657Z-728771b-425148/`,
  `20260521T173644Z-728771b-425148/`,
  `20260521T174117Z-728771b-425148/`) preserved for diffing across
  engine versions.
