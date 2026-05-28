"""Snapshot decision.md into results/<run-id>/ with a manifest."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.provenance import finish_run, start_run

SPIKE = "05_virtualization_scope"
SPIKE_DIR = Path(__file__).resolve().parent
DECISION = SPIKE_DIR / "decision.md"


def main() -> int:
    if not DECISION.exists():
        print(f"missing {DECISION}", file=sys.stderr)
        return 2
    run_dir, manifest = start_run(
        spike=SPIKE, spike_dir=SPIKE_DIR, inputs=[DECISION],
        tools=[], args={}, inputs_kind="design-doc",
        notes="Decision-doc snapshot; status reflects state of decision.md at this run-id.",
    )
    shutil.copy2(DECISION, run_dir / "decision.md")
    # The decision content also becomes the summary the reviewer reads.
    shutil.copy2(DECISION, run_dir / "summary.md")
    finish_run(run_dir, manifest, {})
    print(f"results: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
