"""Run the Spike 1 coverage probes against Fuseki and Oxigraph.

Every response is saved to results/<run-id>/raw/<row>/<engine>.{txt,json}
so the verdict is auditable. The summary table is regenerated from the
JSON results — the markdown is a derived view, not a source of truth.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.provenance import finish_run, start_run

SPIKE = "01_oxigraph_coverage"
SPIKE_DIR = Path(__file__).resolve().parent
INPUTS = SPIKE_DIR / "inputs"

ENDPOINTS = {
    "fuseki": {
        "query": "http://localhost:3030/ds/query",
        "update": "http://localhost:3030/ds/update",
        "gsp": "http://localhost:3030/ds/data",
        "data_load": "http://localhost:3030/ds/data",
        "auth": ("admin", "admin"),
    },
    "oxigraph": {
        "query": "http://localhost:7878/query",
        "update": "http://localhost:7878/update",
        "gsp": "http://localhost:7878/store",
        "data_load": "http://localhost:7878/store?default",
        "auth": None,
    },
}


@dataclass
class ProbeResult:
    row: str
    engine: str
    verdict: str  # pass | partial | fail | manual
    detail: str
    status_code: int | None = None
    raw_path: str | None = None


def load_dataset(engine: str) -> None:
    """Push probe-dataset.ttl into the engine's default graph."""
    ep = ENDPOINTS[engine]
    data = (INPUTS / "probe-dataset.ttl").read_bytes()
    r = requests.post(ep["data_load"], data=data,
                      headers={"Content-Type": "text/turtle"},
                      auth=ep.get("auth"))
    r.raise_for_status()


def run_probe(name: str, spec: dict, engine: str, raw_dir: Path) -> ProbeResult:
    ep = ENDPOINTS[engine]
    auth = ep.get("auth")
    kind = spec.get("kind", "sparql-query")
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_file = raw_dir / f"{engine}.txt"

    try:
        if kind == "sparql-query":
            headers = {"Accept": spec.get("accept", "application/sparql-results+json")}
            r = requests.post(ep["query"], data={"query": spec["body"]}, headers=headers, timeout=30, auth=auth)
        elif kind == "sparql-update":
            r = requests.post(ep["update"], data={"update": spec["body"]}, timeout=30, auth=auth)
        elif kind == "gsp":
            graph = spec["graph"]
            body = (INPUTS / spec["put_body_file"].split("/", 1)[-1]).read_bytes()
            put = requests.put(
                ep["gsp"], params={"graph": graph}, data=body,
                headers={"Content-Type": "text/turtle"}, timeout=30, auth=auth,
            )
            get = requests.get(
                ep["gsp"], params={"graph": graph},
                headers={"Accept": "text/turtle"}, timeout=30, auth=auth,
            )
            out_file.write_text(f"PUT {put.status_code}\n{put.text}\n---\nGET {get.status_code}\n{get.text}")
            ok = put.ok and get.ok and b"writtenVia" in get.content
            return ProbeResult(name, engine, "pass" if ok else "fail",
                               f"PUT={put.status_code} GET={get.status_code}",
                               status_code=get.status_code, raw_path=str(out_file))
        elif kind == "http":
            url = spec["path_template"].format(endpoint=ep["query"])
            r = requests.get(url, headers={"Accept": spec.get("accept", "*/*")}, timeout=30, auth=auth)
        elif kind == "bulk":
            inputs_file = INPUTS / spec["inputs_file"].split("/", 1)[-1]
            if not inputs_file.exists():
                return ProbeResult(name, engine, "manual",
                                   f"input {inputs_file.name} not present (run gen_bulk.py)",
                                   raw_path=None)
            body = inputs_file.read_bytes()
            r = requests.post(
                ep["data_load"], data=body,
                headers={"Content-Type": "application/n-triples"}, timeout=600, auth=auth,
            )
            out_file.write_text(f"{r.status_code}\n{r.text[:2000]}")
            return ProbeResult(name, engine, "pass" if r.ok else "fail",
                               f"bulk load {r.status_code}", status_code=r.status_code,
                               raw_path=str(out_file))
        elif kind == "manual":
            return ProbeResult(name, engine, "manual", spec.get("notes", "manual"))
        else:
            return ProbeResult(name, engine, "fail", f"unknown probe kind: {kind}")
    except requests.RequestException as e:
        out_file.write_text(f"exception: {e}")
        return ProbeResult(name, engine, "fail", str(e), raw_path=str(out_file))

    out_file.write_text(f"{r.status_code}\n{r.text}")
    verdict, detail = evaluate(spec, r)
    return ProbeResult(name, engine, verdict, detail, status_code=r.status_code, raw_path=str(out_file))


def evaluate(spec: dict, r: requests.Response) -> tuple[str, str]:
    rule = spec.get("pass_if", "status-2xx")
    if not r.ok:
        return "fail", f"http {r.status_code}"
    if rule == "status-2xx":
        return "pass", "2xx"
    if rule == "has-bindings":
        try:
            n = len(r.json().get("results", {}).get("bindings", []))
        except Exception:
            return "fail", "non-JSON response"
        return ("pass" if n > 0 else "fail"), f"{n} bindings"
    if rule == "ask-true":
        try:
            return ("pass" if r.json().get("boolean") else "fail"), str(r.json())
        except Exception:
            return "fail", "non-JSON ask response"
    if rule.startswith("triple-count>="):
        n = int(rule.split(">=")[1])
        count = r.text.count(" .\n") + r.text.count(" .")  # cheap N-Triples-ish heuristic
        return ("pass" if count >= n else "partial"), f"~{count} lines, threshold {n}"
    if rule == "status-2xx-and-json":
        try:
            r.json()
            return "pass", "2xx + json"
        except Exception:
            return "partial", "2xx but not JSON"
    if rule == "roundtrip-triples-match":
        return "pass", "GSP roundtrip handled in caller"
    return "partial", f"unrecognised pass_if rule '{rule}'"


def main() -> int:
    probes = yaml.safe_load((SPIKE_DIR / "probes.yaml").read_text())

    run_dir, manifest = start_run(
        spike=SPIKE,
        spike_dir=SPIKE_DIR,
        inputs=list(INPUTS.glob("*")) + [SPIKE_DIR / "probes.yaml", SPIKE_DIR / "feature_matrix.md"],
        tools=["pyoxigraph", "requests", "rdflib"],
        args={},
        notes="Greenfield: coverage gate derived from documented requirements, not runtime usage.",
    )

    raw_root = run_dir / "raw"
    results: list[ProbeResult] = []

    for engine in ("fuseki", "oxigraph"):
        try:
            load_dataset(engine)
        except Exception as e:
            results.append(ProbeResult("_setup_load", engine, "fail", str(e)))
            continue
        for name, spec in probes.items():
            row_dir = raw_root / name
            results.append(run_probe(name, spec, engine, row_dir))

    (run_dir / "probe_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2)
    )

    write_rendered_matrix(run_dir, results)
    write_summary(run_dir, results)
    finish_run(run_dir, manifest, {"counts": tally(results)})
    print(f"results: {run_dir}")
    return 0


def tally(results: list[ProbeResult]) -> dict:
    out: dict[str, dict[str, int]] = {}
    for r in results:
        out.setdefault(r.engine, {}).setdefault(r.verdict, 0)
        out[r.engine][r.verdict] += 1
    return out


def write_rendered_matrix(run_dir: Path, results: list[ProbeResult]) -> None:
    by_row = {(r.row, r.engine): r for r in results}
    src = (SPIKE_DIR / "feature_matrix.md").read_text().splitlines()
    rendered: list[str] = []
    for line in src:
        if line.startswith("| C") and "probe:" in line:
            probe_name = line.split("`probe: ")[1].split("`")[0]
            ox = by_row.get((probe_name, "oxigraph"))
            fu = by_row.get((probe_name, "fuseki"))
            line = (line
                    .replace("_tbd_", _verdict_cell(ox) + "@@OX@@", 1)
                    .replace("_tbd_", _verdict_cell(fu) + "@@FU@@", 1)
                    .replace("@@OX@@", "")
                    .replace("@@FU@@", ""))
        rendered.append(line)
    (run_dir / "feature_matrix.md").write_text("\n".join(rendered))


def _verdict_cell(r: ProbeResult | None) -> str:
    if r is None:
        return "n-a"
    return f"{r.verdict}"


def write_summary(run_dir: Path, results: list[ProbeResult]) -> None:
    counts = tally(results)
    gate_rows = {"sparql-select", "sparql-construct", "sparql-ask", "sparql-describe",
                 "sparql-update-insert", "sparql-update-delete", "gsp-put-get",
                 "sparql-paths", "named-graphs", "io-turtle", "io-jsonld",
                 "io-ntriples", "io-rdfxml", "io-trig", "conneg", "skos-broader",
                 "persistence-restart", "bulk-load"}
    ox_gate = [r for r in results if r.engine == "oxigraph" and r.row in gate_rows]
    failures = [r for r in ox_gate if r.verdict not in ("pass", "manual")]
    verdict = "PASS" if not failures else "FAIL"
    lines = [
        f"# Spike 1 summary — {run_dir.name}",
        "",
        f"**Gating verdict:** {verdict}",
        "",
        "## Counts",
        "",
        f"- Oxigraph: {counts.get('oxigraph', {})}",
        f"- Fuseki:   {counts.get('fuseki', {})}",
        "",
    ]
    if failures:
        lines += ["## Oxigraph gate failures", ""]
        for r in failures:
            lines.append(f"- `{r.row}` — {r.verdict}: {r.detail}")
    (run_dir / "summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
