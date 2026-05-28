# Spike 5 — Virtualization scope decision

**Gates:** Chrontext vs. ONTOP (ADR-004 §3).

Unlike the other four spikes, this one **cannot be automated**. ADR-004
§3 makes Chrontext's viability conditional on the hub's virtualization
scope being narrowed to time-series joins; if general SQL virtualization
is in scope, ONTOP stays and Chrontext is closed out.

The spike's deliverable is therefore a written decision in
`decision.md` — the only spike whose "results" directory holds a single
markdown file plus the manifest. The same provenance helper still runs,
so the decision is timestamped, git-sha-stamped, and reproducible.

## How it runs

`./record.sh` reads `decision.md`, writes a manifest pointing at it,
and snapshots the file into `results/<run-id>/decision.md`. Every time
the decision changes, re-running `record.sh` creates a new run-id; the
history of decisions is therefore preserved without overwrites.

`decision.md` is intentionally a template — sections marked
`TBD (product owner)` are the parts that need a human answer.
