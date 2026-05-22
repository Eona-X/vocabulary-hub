#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

SCALE="${SCALE:-1}"
BENCH_COMMIT="${BENCH_COMMIT:-master}"
TARGET="inputs/gtfs-madrid-bench/scale-${SCALE}"

mkdir -p inputs/gtfs-madrid-bench

if [[ ! -d "$TARGET" ]]; then
  if git ls-remote --exit-code https://github.com/oeg-upm/gtfs-bench.git > /dev/null 2>&1; then
    tmpdir="$(mktemp -d)"
    git clone --depth 1 https://github.com/oeg-upm/gtfs-bench.git "$tmpdir"
    if [[ -d "$tmpdir/$SCALE" ]]; then
      cp -r "$tmpdir/$SCALE" "$TARGET"
      echo "$BENCH_COMMIT" > inputs/gtfs-madrid-bench/.bench_commit
    fi
    rm -rf "$tmpdir"
  fi
fi

if [[ ! -f "$TARGET/mapping.ttl" ]]; then
  echo "GTFS-Madrid-Bench mapping not available at scale=$SCALE; falling back to synthetic." >&2
fi

# Use the spike venv (psutil, rdflib, maplib live there) and put uv on
# PATH for Morph-KGC's per-test `uv run --isolated`.
export PATH="$(cd .. && pwd)/venv/bin:$PATH"
exec env SCALE="$SCALE" ../.venv/bin/python bench.py
