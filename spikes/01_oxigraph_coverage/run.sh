#!/usr/bin/env bash
# Spike 1 entry point. Assumes docker compose stack is up.
set -euo pipefail
cd "$(dirname "$0")"

# Generate the bulk fixture deterministically if it isn't already there.
if [[ ! -f inputs/bulk-100k.nt ]]; then
  python inputs/gen_bulk.py 100000 > inputs/bulk-100k.nt
fi

exec python probe.py
