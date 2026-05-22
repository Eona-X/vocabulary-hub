# Spike 3 — Maplib RML conformance runner

**Gates:** L3 ETL swap (ADR-004 §2).

## What this spike answers

ADR-004 requires "run the RML test suite. Output: pass-rate vs.
Morph-KGC." This spike runs the upstream
[`kg-construct/rml-test-cases`](https://github.com/kg-construct/rml-test-cases)
test suite — the test suite the Morph-KGC project itself uses — on both
engines under consideration and emits per-test verdicts.

## Engines considered and rejected

**Rossete-RDF** (RubenCid35/rossete-rdf v0.1.1) — Rust-native RML
materialiser, evaluated as an alternative to Maplib for the L3 swap.
Rejected:

- **Out-of-the-box conformance: 0 / 324.** The hand-rolled Turtle
  tokeniser doesn't accept the W3C-canonical `@prefix x: <iri> .`
  (whitespace before the terminator dot) used by every kg-construct
  mapping. The bundled `examples/mappings/` use `@prefix x: <iri>.` —
  the bug was never exercised upstream.
- **Engine ceiling with preprocessing: 7 / 324 (2.2%, 4.9% of testable
  cases).** Rewriting mappings to the dialect rossete accepts
  (whitespace fix + `<TriplesMap1>` → `<#TriplesMap1>`) makes 7
  trivial single-table CSV/JSON tests pass. XML logical sources, joins,
  graph maps, language tags, and most complex term-maps still panic in
  the parser.
- **Per-test wall time on passes: 8 ms vs. Morph-KGC's 949 ms (~118×
  faster).** The performance gap is real but on the feature-trivial
  subset only — exactly the cases the Vocabulary Hub doesn't need
  performance on. Hub-relevant features (joins on GTFS, XPath on
  schedule extensions) aren't supported at all.
- **Upstream is abandoned.** Last release Feb 2022. The `1.0` branch
  (Jan 2025) and `refactor/v0.2.0-rewrite` (Feb 2026) are parser-only
  WIPs with no materialisation path — they cannot run the suite.

The "take ownership" cost is rewriting the Turtle parser plus
implementing the missing RML features — a multi-engineer-month
investment with no clear advantage over Maplib at the same level of
investment. Discarded.

Full per-test rossete-pp results: `results/20260521T224014Z-994f575-eb50a7/`.

## Engines compared in the live spike

- **Morph-KGC** (Python, the current L3 ETL incumbent)
- **Maplib** (Rust, the ADR-004 candidate)
- **RMLMapper-Java** v8.1.0 (the reference RML.io implementation; the
  bar Morph-KGC's own conformance numbers are measured against)

## How it runs

`run.sh` does the following:

1. Fetches a pinned commit of `rml-test-cases` into
   `inputs/rml-test-cases/` (commit SHA recorded in the manifest, so a
   re-run with a different upstream snapshot is a different
   `inputs.files[].sha256` and therefore a different `run-id`).
2. Fetches a pinned release of `rmlmapper-java` (fat jar) into
   `inputs/rmlmapper-<version>-<build>-all.jar`.
3. For each test case (each has `mapping.ttl`, source data files, and an
   expected `output.nq` / `output.nt`):
   1. Runs Morph-KGC.
   2. Runs Maplib.
   3. Runs RMLMapper-Java.
   4. Canonicalises each engine's output (sorted N-Quads after rdflib
      isomorphism normalisation).
   5. Diffs against the canonicalised expected output.
4. Writes:
   - `results/<run-id>/verdicts.json` — per-test `{engine, test, verdict,
     diff_path}` records.
   - `results/<run-id>/raw/<test-id>/{morph,maplib,rmlmapper}.nt` — actual output.
   - `results/<run-id>/raw/<test-id>/{morph,maplib,rmlmapper}.diff` — line diff
     against the expected canonical output (empty file ⇒ pass).
   - `results/<run-id>/summary.md` — pass-rate per engine, list of tests
     where the two engines diverge.

## Why save everything

A pass-rate number alone is not enough — the ADR reviewer needs to see
*which* tests Maplib fails to decide whether those failure modes affect
the hub. The per-test raw output and diff make that review possible
without re-running the spike.

## Re-running

```bash
./run.sh                # fetches the test suite + rmlmapper jar once, then runs all engines
./run.sh --refresh-tests   # re-clone the test suite at the latest commit
```

Override pinned versions via env: `SUITE_COMMIT=<sha> RMLMAPPER_VERSION=8.1.0 RMLMAPPER_BUILD=r380 ./run.sh`.
