"""Aggregate the latest result for every (scale, framework) pair into a
Markdown report at spikes/02_oxigraph_bench/SYNTHESIS.md.

Picks the most recent run per (scale, framework) — earlier runs are ignored.
Cross-checks row counts across engines per query at each scale.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "SYNTHESIS.md"


def load_results() -> dict[str, dict[str, dict]]:
    """Returns {scale: {framework: result_dict}} keeping only the most recent
    run per (scale, framework)."""
    latest_ts: dict[tuple[str, str], str] = {}
    payloads: dict[tuple[str, str], dict] = {}
    for run_dir in sorted(RESULTS.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        scale = manifest["config"]["scale"]
        ts = run_dir.name  # sorts lexicographically by UTC stamp
        for fw_dir in (run_dir / "raw").iterdir():
            if not fw_dir.is_dir():
                continue
            result_file = fw_dir / "result.json"
            if not result_file.exists():
                continue
            r = json.loads(result_file.read_text())
            fw = r.get("framework", fw_dir.name)
            key = (scale, fw)
            if key not in latest_ts or ts > latest_ts[key]:
                latest_ts[key] = ts
                payloads[key] = {"manifest": manifest, "result": r, "run_id": ts}

    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for (scale, fw), payload in payloads.items():
        out[scale][fw] = payload
    return dict(out)


SCALE_ORDER = ["100k", "1m", "10m"]
FRAMEWORK_ORDER = [
    "maplib",
    "oxigraph",
    "oxigraph_fork",
    "rdflib",
    "fuseki_tdb2",
    "qlever",
    "virtuoso",
]


def fmt_ms(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds == float("inf"):
        return "—"
    ms = seconds * 1000
    if ms < 0.1:
        return f"{ms:.3f}"
    if ms < 10:
        return f"{ms:.2f}"
    if ms < 1000:
        return f"{ms:.1f}"
    return f"{ms:,.0f}"


def fmt_bytes(b: int | None) -> str:
    if not b:
        return "—"
    if b >= 1 << 30:
        return f"{b / (1 << 30):.2f} GiB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.1f} MiB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f} KiB"
    return f"{b} B"


def render_scale(scale: str, by_fw: dict[str, dict]) -> str:
    fws = [fw for fw in FRAMEWORK_ORDER if fw in by_fw] + sorted(
        fw for fw in by_fw if fw not in FRAMEWORK_ORDER
    )
    lines: list[str] = []
    lines.append(f"## {scale}\n")

    # Pull union of query IDs from all frameworks
    qids: list[str] = []
    seen: set[str] = set()
    for fw in fws:
        for qid in by_fw[fw]["result"].get("queries", {}):
            if qid not in seen:
                qids.append(qid)
                seen.add(qid)
    qids.sort()

    # --- Headline timing table (best of 3, ms) ---
    lines.append("### Timing (best of 3, ms)\n")
    header = "| Query | " + " | ".join(fws) + " |"
    sep = "|" + "---|" * (len(fws) + 1)
    lines.append(header)
    lines.append(sep)
    lines.append("| **load** | " + " | ".join(
        fmt_ms(by_fw[fw]["result"].get("load_s")) for fw in fws
    ) + " |")
    for qid in qids:
        cells = []
        for fw in fws:
            q = by_fw[fw]["result"].get("queries", {}).get(qid)
            if q is None:
                cells.append("skipped")
            elif "error" in q:
                cells.append("ERROR")
            elif q.get("timed_out"):
                cells.append("TIMEOUT")
            else:
                cells.append(fmt_ms(q.get("best_s")))
        lines.append(f"| {qid} | " + " | ".join(cells) + " |")
    lines.append("")

    # --- Row-count cross-check ---
    lines.append("### Row count cross-check\n")
    lines.append(header)
    lines.append(sep)
    for qid in qids:
        rc_cells: list[str] = []
        seen_counts: set[int] = set()
        for fw in fws:
            q = by_fw[fw]["result"].get("queries", {}).get(qid)
            if q is None or "row_count" not in q:
                rc_cells.append("—")
                continue
            rc = q["row_count"]
            rc_cells.append(str(rc))
            if rc >= 0:
                seen_counts.add(rc)
        marker = " ✅" if len(seen_counts) == 1 else " ⚠ DISAGREE" if len(seen_counts) > 1 else ""
        lines.append(f"| {qid}{marker} | " + " | ".join(rc_cells) + " |")
    lines.append("")

    # --- p50/p95 detail ---
    lines.append("### p50 / p95 (ms)\n")
    h2 = "| Query | " + " | ".join(f"{fw} p50" for fw in fws) + " | " + " | ".join(f"{fw} p95" for fw in fws) + " |"
    s2 = "|" + "---|" * (1 + 2 * len(fws))
    lines.append(h2)
    lines.append(s2)
    for qid in qids:
        p50s = []
        p95s = []
        for fw in fws:
            q = by_fw[fw]["result"].get("queries", {}).get(qid)
            if q is None or "error" in q or q.get("timed_out"):
                p50s.append("—")
                p95s.append("—")
            else:
                p50s.append(fmt_ms(q.get("p50_s")))
                p95s.append(fmt_ms(q.get("p95_s")))
        lines.append(f"| {qid} | " + " | ".join(p50s) + " | " + " | ".join(p95s) + " |")
    lines.append("")

    # --- Memory & storage ---
    lines.append("### Memory & storage\n")
    lines.append("| Metric | " + " | ".join(fws) + " |")
    lines.append(sep)
    lines.append("| peak RSS | " + " | ".join(
        fmt_bytes(by_fw[fw]["result"].get("rss_peak_bytes")) for fw in fws
    ) + " |")
    lines.append("| store on disk | " + " | ".join(
        fmt_bytes(by_fw[fw]["result"].get("store_bytes_on_disk")) for fw in fws
    ) + " |")
    lines.append("")

    # --- Notes ---
    notes: list[str] = []
    for fw in fws:
        r = by_fw[fw]["result"]
        skipped = r.get("config", {}).get("skipped_queries") or []
        skipped = skipped or by_fw[fw]["manifest"].get("config", {}).get("skipped_queries") or []
        if skipped:
            notes.append(f"- **{fw}** skipped queries: {', '.join(skipped)} (would not complete within budget at this scale).")
        for qid, q in r.get("queries", {}).items():
            if isinstance(q, dict) and "error" in q:
                notes.append(f"- **{fw} {qid}**: `{q['error']}` — `{q.get('body','').splitlines()[0] if q.get('body') else q.get('message','')}`")
            elif isinstance(q, dict) and q.get("timed_out"):
                notes.append(f"- **{fw} {qid}**: timed out after first sample (>300 s).")
    if notes:
        lines.append("### Notes\n")
        lines.extend(notes)
        lines.append("")

    # --- Provenance ---
    lines.append("### Run provenance\n")
    lines.append("| Framework | Run dir |")
    lines.append("|---|---|")
    for fw in fws:
        lines.append(f"| {fw} | `results/{by_fw[fw]['run_id']}/raw/{fw}/` |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    by_scale = load_results()
    scales_present = [s for s in SCALE_ORDER if s in by_scale] + sorted(
        s for s in by_scale if s not in SCALE_ORDER
    )

    out: list[str] = []
    out.append("# Spike 02 — Synthesis of L1/L2 bench results\n")
    out.append(
        "Auto-generated from the latest run per (scale, framework) under `results/`. "
        "Regenerate with `python spikes/02_oxigraph_bench/harness/synthesize.py`.\n"
    )
    out.append("Methodology: best-of-3 after a warmup; per-query timeout 300 s; "
               "row_count is the parsed `results.bindings` length (HTTP) or "
               "materialized iteration count (in-process). Peak RSS via psutil "
               "(in-process) or `docker stats` (Docker-backed).\n")

    for scale in scales_present:
        out.append(render_scale(scale, by_scale[scale]))

    OUT.write_text("\n".join(out))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
