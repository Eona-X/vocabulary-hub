# ADR-004 validation spikes — synthesis

> Synthesis date: 2026-05-25
> Branch: `impl/adr-004`
> Source-of-truth: per-spike `RESULT.md` / `FINDINGS.md` / `decision.md` and
> the run-ids cited below. This document does not introduce new evidence;
> it consolidates the five spike verdicts so an ADR reviewer can take
> ADR-004 from Proposed → Accepted in one read.

## Verdicts at a glance

| # | Spike | Gates | Verdict | Effect on ADR-004 |
|---|---|---|---|---|
| 1 | Oxigraph coverage | L1/L2 swap | **PASS** | Supports the swap |
| 2 | Oxigraph vs Fuseki benchmark | L1/L2 swap | **PASS** (deployment-realistic) | Supports the swap, with amendments |
| 3 | Maplib RML conformance | L3 ETL swap | **FAIL** | Rejects the swap — Morph-KGC stays |
| 4 | Maplib materialisation benchmark | L3 ETL swap | **FAIL (coverage-gated)** | Confirms §2 rejection; "47×–182×" claim unreproducible |
| 5 | Virtualization scope | Chrontext vs ONTOP | **OPEN** (working hypothesis: no virtualization required) | Awaits product-owner input |

ADR-004 §1 (L1/L2 Jena → Oxigraph) is supported. ADR-004 §2 (Morph-KGC → Maplib) is rejected. ADR-004 §3 (ONTOP → Chrontext) is gated on an unanswered scope question.

## Spike 1 — Oxigraph coverage ✅

Run-id: [`20260521T183330Z-ae0a328-c4b749`](01_oxigraph_coverage/results/20260521T183330Z-ae0a328-c4b749/) — Oxigraph 0.5.8 vs Jena/Fuseki 5.1.0.

- 18 / 20 auto-probed capabilities pass on both engines.
- The only failing row (`sparql-service`) reproduces on Fuseki too — network-bound, not engine-bound.
- The JSON-LD CONSTRUCT gap that blocked the prior 0.4.7 run is **closed** on 0.5.8 (`Accept: application/ld+json` now returns 200).
- Manual-only rows (SHACL, OWL 2 RL, RDFS entailment, persistence-restart, HTTP auth) belong to ADR-002 / deployment hardening, not to the L1/L2 engine choice.

Reviewer actions: pin Oxigraph ≥ 0.5.8; drop the prior "JSON-LD transcoding workaround" from ADR-004 §1; decide whether SPARQL `SERVICE` federation is a documented hub requirement (working assumption: no).

## Spike 2 — Oxigraph vs Fuseki benchmark ✅

Run-ids: [`20260521T182850Z`](02_oxigraph_bench/results/20260521T182850Z-ae0a328-425148/) (tmpfs) and [`20260521T182913Z`](02_oxigraph_bench/results/20260521T182913Z-ae0a328-425148/) (disk, deployment-realistic). 100k-triple synthetic SKOS taxonomy, 8 hub-shaped queries, 50 timed iterations, 4 Hz RSS sampling.

| Dimension | Result | Notes |
|---|---|---|
| Peak RSS (disk) | Oxigraph 173 MB vs Fuseki 1272 MB | **~7.34×**, not the 10× claimed in ADR-004 §1 |
| Bulk load (100k triples) | 166 966 vs 162 200 t/s | **Tied** — prior 5.9× Fuseki advantage was an in-mem vs RocksDB artefact |
| UPDATE INSERT (`q07`) | 1.1 ms vs 45.3 ms | **~41×** in Oxigraph's favour — TDB2 durability sync cost |
| Property-path & CONSTRUCT (`q02`, `q04`, `q08`) | 3–4× in Oxigraph's favour | |
| Cross-named-graph COUNT (`q06`) | 24.7 ms vs 4.5 ms | **5.5× regression** on Oxigraph (file upstream) |
| Label-scan with FILTER (`q01`) | 62.9 ms vs 30.3 ms | 2× Fuseki edge after Jena 5.1.0's ARQ improvements |

Caveats: public-reference workload, single-threaded client, single dataset scale, no SHACL / reasoning load.

Reviewer actions: amend ADR-004 §1 "~10× memory" → "~7× memory"; pin Oxigraph ≥ 0.5.8 and Jena ≥ 5.1.0; acknowledge `q06` as the one workload shape where Oxigraph is materially slower; file the Oxigraph upstream issue for cross-named-graph aggregation.

## Spike 3 — Maplib RML conformance ❌

Run-id: [`20260521T225750Z-994f575-eb50a7`](03_maplib_rml_conformance/results/20260521T225750Z-994f575-eb50a7/) over the upstream `kg-construct/rml-test-cases` suite (324 tests).

| Engine | pass | fail | error | skipped | pass-rate |
|---|---:|---:|---:|---:|---:|
| Morph-KGC | 87 | 12 | 40 | 185 | **26.9%** |
| Maplib | 0 | 0 | 144 | 180 | **0.0%** |
| RMLMapper-Java (reference) | 84 | 18 | 39 | 183 | 25.9% |

Maplib does not run a single RML test case. Root cause is that its mapping ingestion is stOTTR, not RML/R2RML — every test errors at parse time. The two near-misses considered as alternatives were also rejected upstream of the suite:

- **rossete-rdf** — engine ceiling 7/324 (4.9% of testable cases) after hand-fixing the Turtle tokeniser; upstream abandoned since Feb 2022.
- **MappingLoom-rs** — not a materialisation engine (emits `.dot` mapping-plan graphs, no RDF output); wrong layer for L3.

Morph-KGC's 26.9% and RMLMapper-Java's 25.9% are within run-to-run noise of each other — Morph-KGC sits at the RML-reference bar on this suite snapshot, which is the position L3 currently needs to keep.

Reviewer action: reject ADR-004 §2; keep Morph-KGC as L3 ETL.

## Spike 4 — Maplib materialisation benchmark ❌ (coverage-gated)

Run-id: [`20260522T083109Z-98dac21-32d201`](04_maplib_bench/results/20260522T083109Z-98dac21-32d201/) (Maplib 0.20.x).

| Engine | ok | wall (s) | peak RSS (MB) | triples |
|---|---|---:|---:|---:|
| Morph-KGC | ✓ | 1.79 | 254.9 | 10 |
| Maplib | ✗ | 0.14 | 0.0 | 0 |

Maplib fails at template parse time (`expected IRI parsing failed`) — the same stOTTR-vs-RML mismatch that produced 0/324 in Spike 3, hit on a single mapping. GTFS-Madrid-Bench could not be exercised through the published path (`vig-1.8.1.jar` needs a live MySQL; the Docker image is interactive only); a synthetic fallback was used. The ADR-004 §2 "47×–182× faster than Morph-KGC on GTFS-Madrid-Bench" claim is **not refuted but is unreproducible on this host** — Maplib never enters the timed section, and the cited number is single-benchmark, single-vendor, and tied to an earlier API/template scope than 0.20.x.

Under ADR-000's `coverage → maturity → memory → performance` ranking, a candidate that fails coverage is rejected regardless of performance. Spike 4 confirms Spike 3.

What survives for re-use: the harness is engine-agnostic (RSS sampler, canonical count+hash diff, synthetic fallback, manifest machinery). A future RML-capable Rust engine slots in as one `bench_<engine>` function — re-using this for the next L3 candidate costs less than a day.

## Spike 5 — Virtualization scope ⏸

[`05_virtualization_scope/decision.md`](05_virtualization_scope/decision.md) — owner TBD (product owner), status **Open**.

Question: does the hub need **general SQL virtualization** (ONTOP territory), only **time-series/analytical joins** (Chrontext territory), or **no virtualization at all**?

Evidence in repo:

- IDS-RAM §3.5.6 describes a publication/lookup service over native RDF — no virtualization mandate.
- ADR-002's runtime IRI dereferencing is served by Jena/Oxigraph + reasoner, not by ONTOP/Chrontext.
- ADR-001 §Required capabilities does not list relational source federation.
- The hub is greenfield — nothing in repo today depends on relational virtualization.

Working hypothesis: **no virtualization required**; close ADR-004 §3 as "L3 virtualization not required; both ONTOP and Chrontext out of scope," and revise ADR-003 to drop the virtualization half. If a product-owner use case lands, re-open and run a Spikes-1–4-shaped gate against Chrontext.

## Consolidated recommendation to the ADR reviewer

1. **Accept ADR-004 §1 (L1/L2 swap).** Pin Oxigraph ≥ 0.5.8 and (where Fuseki survives at all) Jena ≥ 5.1.0. Amend the "10× memory" claim to "~7× memory." Drop the JSON-LD transcoding workaround. Record `q06` (cross-named-graph COUNT) as a known Oxigraph regression and open the upstream issue.
2. **Reject ADR-004 §2 (L3 ETL swap).** Morph-KGC stays. Document Maplib's coverage gap (stOTTR, not RML) and the two adjacent Rust crates already discarded (`rossete-rdf`, `mappingloom-rs`) so the question is not re-litigated. Mark the published "47×–182×" speedup as unreproduced and out of scope.
3. **Hold ADR-004 §3 pending product-owner input** on the virtualization-scope question. Default to closing as "not required" if no answer lands before the next ADR review.
4. **Move ADR-004 from Proposed → Accepted** with §1 accepted, §2 rejected (with rationale), §3 conditional and time-boxed against the §5 decision. The bundled-PR shape matches how this branch has been worked; do not split.

## Provenance

Every verdict above is traceable to a committed `results/<run-id>/` directory containing `manifest.json` (UTC timestamp, git SHA, host, tool versions, input file hashes, `inputs.kind`), the raw per-engine outputs, and a `summary.md`. Historical runs (pre-version-bump for Spikes 1–2, the rossete-rdf and per-engine staging runs for Spike 3) are preserved alongside the current ones for diff review.
