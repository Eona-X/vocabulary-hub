"""RML conformance runner for Maplib and Morph-KGC.

Each test in the rml-test-cases suite is a directory containing:
  - mapping.ttl     RML mapping
  - source files    CSV / JSON / XML referenced from the mapping
  - output.nq       expected output (or `expected_invalid` to assert error)

For every test, both engines are invoked, output is canonicalised via
rdflib graph isomorphism, and the diff against expected is saved.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.provenance import finish_run, start_run

SPIKE = "03_maplib_rml_conformance"
SPIKE_DIR = Path(__file__).resolve().parent
TESTS_DIR = SPIKE_DIR / "inputs" / "rml-test-cases" / "test-cases"

# Rossete-RDF was evaluated and discarded — see README "Engines considered
# and rejected". Its runner and preprocessor live in git history.
ENGINES = ("morph", "maplib", "rmlmapper")

# kg-construct mappings declare `@base <http://example.com/base/>`. The
# RMLMapper CLI doesn't honour the in-file @base for term-map IRI expansion
# unless -b is set explicitly, so pass it through.
RMLMAPPER_BASE_IRI = "http://example.com/base/"


@dataclass
class Verdict:
    test_id: str
    engine: str
    verdict: str  # pass | fail | error | skipped
    detail: str
    raw_path: str | None = None
    diff_path: str | None = None
    duration_ms: float | None = None


SQL_BACKED_SUFFIXES = ("-MySQL", "-PostgreSQL", "-SQLServer")


def is_sql_backed(test_dir: Path) -> bool:
    """Tests whose id ends in -MySQL/-PostgreSQL/-SQLServer need a live SQL
    database neither engine can reach in this harness; mark them skipped
    rather than error so the pass-rate reflects what's actually testable."""
    return test_dir.name.endswith(SQL_BACKED_SUFFIXES)


def discover_tests() -> list[Path]:
    if not TESTS_DIR.exists():
        return []
    return sorted(p for p in TESTS_DIR.iterdir() if p.is_dir() and (p / "mapping.ttl").exists())


def run_morph(test_dir: Path, out_file: Path) -> tuple[bool, str]:
    """Morph-KGC reads a config.ini that points at the mapping + output."""
    cfg = (
        f"[CONFIGURATION]\noutput_file={out_file}\n"
        f"[Dataset1]\nmappings={test_dir / 'mapping.ttl'}\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
        f.write(cfg)
        cfg_path = f.name
    try:
        proc = subprocess.run(
            ["uv", "run", "--isolated", "--with", "morph-kgc==2.10.0",
             "python", "-m", "morph_kgc", cfg_path],
            cwd=test_dir, capture_output=True, text=True, timeout=300,
        )
        return proc.returncode == 0, (proc.stdout + proc.stderr)
    except Exception as e:
        return False, f"exception: {e}\n{traceback.format_exc()}"


def run_maplib(test_dir: Path, out_file: Path) -> tuple[bool, str]:
    """Maplib 0.20.18 has no RML ingestion. Its mapping language is stOTTR
    (Model.read_template) and the only template-generation helper goes
    from an RDFS/OWL ontology to OTTR — not from an RML mapping. So
    pointing read_template at an RML mapping.ttl fails at parse time
    (stOTTR expects `@prefix`/`<iri> [ ... ] :: name`, not `rr:TriplesMap`).
    That failure IS the spike's finding for ADR-004: swapping
    Morph-KGC for Maplib is not a drop-in — every RML mapping in the hub
    would have to be re-authored as an OTTR template.

    The runner still calls read_template per-test so the error mode is
    captured in the per-test log rather than asserted in code, and so
    that if any test happens to ship a file that parses as stOTTR (none
    do today) it would surface as a pass."""
    try:
        from maplib import Model
        m = Model()
        m.read_template(str(test_dir / "mapping.ttl"))
        # If parsing somehow succeeded, materialise the default graph.
        m.write(str(out_file), format="ntriples")
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


def run_rmlmapper(test_dir: Path, out_file: Path) -> tuple[bool, str]:
    """RMLMapper-Java (the reference implementation maintained by RML.io).

    Invoked as a fat-jar CLI per-test. The JVM startup tax is ~1s/test but
    we eat it rather than spinning up a long-lived server, because the
    point of the spike is per-test conformance, not throughput, and a
    sub-process keeps test isolation simple."""
    jar = os.environ.get("RMLMAPPER_JAR")
    if not jar or not Path(jar).exists():
        return False, "RMLMAPPER_JAR not set or jar missing; run run.sh"
    try:
        proc = subprocess.run(
            ["java", "-jar", jar,
             "-m", str(test_dir / "mapping.ttl"),
             "-o", str(out_file),
             "-s", "nquads",
             "-b", RMLMAPPER_BASE_IRI],
            cwd=test_dir, capture_output=True, text=True, timeout=300,
        )
        # RMLMapper exits 0 even when it writes nothing (e.g. empty source
        # → empty graph). The diff stage is what determines pass/fail.
        return proc.returncode == 0, (proc.stdout + proc.stderr)
    except Exception as e:
        return False, f"exception: {e}\n{traceback.format_exc()}"


def load_graph(path: Path):
    """Parse N-Quads / N-Triples / Turtle into an rdflib Graph, projecting
    quads down to triples (kg-construct tests use the default graph only),
    and normalise `"x"^^xsd:string` to plain `"x"` so the isomorphism
    check matches RDF 1.1 semantics. rdflib 7.x's isomorphic() treats the
    two forms as distinct even though the spec considers them equal; some
    engines (rossete-rdf) always stamp the explicit datatype, others
    (morph-kgc) omit it."""
    import rdflib
    from rdflib import Literal
    from rdflib.namespace import XSD
    suffix = path.suffix.lower()
    if suffix == ".nq":
        ds = rdflib.Dataset()
        ds.parse(str(path), format="nquads")
        raw = rdflib.Graph()
        for s, p, o, _ in ds.quads((None, None, None, None)):
            raw.add((s, p, o))
    else:
        raw = rdflib.Graph()
        fmt = {".ttl": "turtle", ".nt": "ntriples"}.get(suffix)
        raw.parse(str(path), format=fmt) if fmt else raw.parse(str(path))
    g = rdflib.Graph()
    for s, p, o in raw:
        if isinstance(o, Literal) and o.datatype == XSD.string:
            o = Literal(str(o))
        g.add((s, p, o))
    return g


def canonical_nt(g) -> str:
    """Stable, bnode-canonicalised N-Triples string for diffing.

    rdflib.compare.to_isomorphic returns an IsomorphicGraph whose blank
    nodes are renamed to a canonical form derived from graph structure,
    so two graphs that differ only in bnode IDs serialise identically."""
    from rdflib.compare import to_isomorphic
    iso = to_isomorphic(g)
    return "\n".join(sorted(l for l in iso.serialize(format="nt").splitlines() if l.strip()))


def diff_against_expected(actual_path: Path, expected_path: Path, diff_path: Path) -> bool:
    try:
        from rdflib.compare import isomorphic
        a_g = load_graph(actual_path)
        e_g = load_graph(expected_path)
    except Exception as ex:
        diff_path.write_text(f"parse error: {ex}\n")
        return False
    if isomorphic(a_g, e_g):
        # Includes the legitimate "both empty" case (e.g. RMLTC0000 — empty
        # CSV, empty expected output). Empty-equals-empty is a pass.
        diff_path.write_text("")
        return True
    a = canonical_nt(a_g)
    e = canonical_nt(e_g)
    diff_path.write_text(
        f"--- expected\n+++ actual\n"
        f"-- expected ({len(e.splitlines())} lines) --\n{e}\n"
        f"-- actual ({len(a.splitlines())} lines) --\n{a}\n"
    )
    return False


def run_one(test_dir: Path, run_dir: Path) -> list[Verdict]:
    test_id = test_dir.name
    raw_dir = run_dir / "raw" / test_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    expected = test_dir / "output.nq"
    if not expected.exists():
        expected = test_dir / "output.nt"

    verdicts: list[Verdict] = []
    if is_sql_backed(test_dir):
        for engine in ENGINES:
            verdicts.append(Verdict(test_id, engine, "skipped",
                                    "SQL-backed test; no live database in harness"))
        return verdicts

    runners = (("morph", run_morph), ("maplib", run_maplib), ("rmlmapper", run_rmlmapper))
    for engine, runner in runners:
        out_file = raw_dir / f"{engine}.nt"
        t0 = time.perf_counter()
        ok, log = runner(test_dir, out_file)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        (raw_dir / f"{engine}.log").write_text(log)
        if not ok:
            verdicts.append(Verdict(test_id, engine, "error", log[:500].strip(),
                                    raw_path=str(out_file), duration_ms=dur_ms))
            continue
        if not expected.exists():
            verdicts.append(Verdict(test_id, engine, "skipped",
                                    "no expected output present",
                                    raw_path=str(out_file), duration_ms=dur_ms))
            continue
        diff_path = raw_dir / f"{engine}.diff"
        passed = diff_against_expected(out_file, expected, diff_path)
        verdicts.append(Verdict(
            test_id, engine, "pass" if passed else "fail",
            "ok" if passed else "graphs differ",
            raw_path=str(out_file), diff_path=str(diff_path), duration_ms=dur_ms,
        ))
    return verdicts


def main() -> int:
    tests = discover_tests()
    if not tests:
        print(f"no tests found under {TESTS_DIR}; run run.sh to fetch the suite",
              file=sys.stderr)
        return 2

    run_dir, manifest = start_run(
        spike=SPIKE, spike_dir=SPIKE_DIR,
        inputs=[*TESTS_DIR.rglob("mapping.ttl")],
        tools=["maplib", "morph-kgc", "rmlmapper-java", "rdflib"],
        args={"n_tests": len(tests)},
        inputs_kind="public-reference",
        notes="rml-test-cases pinned via run.sh; see manifest input hashes for commit.",
    )

    all_verdicts: list[Verdict] = []
    for t in tests:
        all_verdicts.extend(run_one(t, run_dir))

    (run_dir / "verdicts.json").write_text(
        json.dumps([asdict(v) for v in all_verdicts], indent=2)
    )
    write_summary(run_dir, all_verdicts)
    finish_run(run_dir, manifest, {"tests": len(tests)})
    print(f"results: {run_dir}")
    return 0


def write_summary(run_dir: Path, verdicts: list[Verdict]) -> None:
    counts: dict[str, dict[str, int]] = {e: {} for e in ENGINES}
    for v in verdicts:
        counts[v.engine][v.verdict] = counts[v.engine].get(v.verdict, 0) + 1
    total = {e: sum(c.values()) for e, c in counts.items()}
    pass_rate = {e: counts[e].get("pass", 0) / total[e] if total[e] else 0.0
                 for e in counts}

    by_test: dict[str, dict[str, str]] = {}
    for v in verdicts:
        by_test.setdefault(v.test_id, {})[v.engine] = v.verdict
    divergent = []
    for t, by_engine in by_test.items():
        # A test is "divergent" if the engines don't agree on the verdict —
        # i.e. at least two engines produced different outcomes.
        if len(set(by_engine.get(e, "?") for e in ENGINES)) > 1:
            divergent.append((t, *(by_engine.get(e, "?") for e in ENGINES)))

    # Wall-time per engine, split into successful runs vs. all runs, so
    # the perf comparison isn't dominated by timeouts on failing engines.
    durs_all: dict[str, list[float]] = {e: [] for e in ENGINES}
    durs_pass: dict[str, list[float]] = {e: [] for e in ENGINES}
    for v in verdicts:
        if v.duration_ms is None:
            continue
        durs_all[v.engine].append(v.duration_ms)
        if v.verdict == "pass":
            durs_pass[v.engine].append(v.duration_ms)

    def _mean(xs: list[float]) -> str:
        return f"{(sum(xs)/len(xs)):.0f}" if xs else "-"

    lines = [
        f"# Spike 3 summary — {run_dir.name}",
        "",
        "| engine | pass | fail | error | skipped | total | pass-rate | mean ms (pass) | mean ms (all) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for e in ENGINES:
        c = counts[e]
        lines.append(
            f"| {e} | {c.get('pass',0)} | {c.get('fail',0)} | {c.get('error',0)} | "
            f"{c.get('skipped',0)} | {total[e]} | {pass_rate[e]:.1%} | "
            f"{_mean(durs_pass[e])} | {_mean(durs_all[e])} |"
        )
    lines += ["", "## Divergent tests (engines disagree)", ""]
    if not divergent:
        lines.append("_none_")
    else:
        lines.append("| test | " + " | ".join(ENGINES) + " |")
        lines.append("|---" * (1 + len(ENGINES)) + "|")
        for row in sorted(divergent):
            lines.append("| " + " | ".join(row) + " |")
    (run_dir / "summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
