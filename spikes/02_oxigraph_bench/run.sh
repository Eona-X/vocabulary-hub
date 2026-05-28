#!/usr/bin/env bash
# Spike 2 entry point.
#   VARIANT=tmpfs ./run.sh    # engine-only (default)
#   VARIANT=disk  ./run.sh    # deployment-realistic
# Brings up the matching Docker Compose profile before benching.
set -euo pipefail
cd "$(dirname "$0")"

VARIANT="${VARIANT:-tmpfs}"
case "$VARIANT" in
  tmpfs|disk) ;;
  *) echo "VARIANT must be 'tmpfs' or 'disk', got '$VARIANT'" >&2; exit 2 ;;
esac

# Make sure no leftover containers from the other variant are bound to
# the shared ports / container names.
docker compose -f ../docker/docker-compose.yml --profile tmpfs --profile disk down >/dev/null 2>&1 || true
docker compose -f ../docker/docker-compose.yml --profile "$VARIANT" up -d

# Give the JVM a moment; Oxigraph is ready almost immediately.
for i in 1 2 3 4 5 6 7 8 9 10; do
  ox=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:7878/ 2>/dev/null || echo down)
  fu=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:3030/'$'/ping 2>/dev/null || echo down)
  [[ "$ox" == "200" && "$fu" == "200" ]] && break
  sleep 2
done

mkdir -p inputs
if [[ ! -e inputs/bulk-skos.nt ]]; then
  if [[ -f ../01_oxigraph_coverage/inputs/bulk-100k.nt ]]; then
    ln -s ../../01_oxigraph_coverage/inputs/bulk-100k.nt inputs/bulk-skos.nt
  else
    python ../01_oxigraph_coverage/inputs/gen_bulk.py 100000 > inputs/bulk-skos.nt
  fi
fi

exec env VARIANT="$VARIANT" ../.venv/bin/python bench.py
