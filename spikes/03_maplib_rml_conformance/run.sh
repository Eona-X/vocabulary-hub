#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Pin the rml-test-cases commit so re-runs hash-stable. Bump deliberately.
SUITE_COMMIT="${SUITE_COMMIT:-master}"
TARGET="inputs/rml-test-cases"

# Pin rmlmapper-java release. Bumping requires re-running the suite.
RMLMAPPER_VERSION="${RMLMAPPER_VERSION:-8.1.0}"
RMLMAPPER_BUILD="${RMLMAPPER_BUILD:-r380}"
RMLMAPPER_JAR="inputs/rmlmapper-${RMLMAPPER_VERSION}-${RMLMAPPER_BUILD}-all.jar"

mkdir -p inputs
if [[ "${1:-}" == "--refresh-tests" ]] || [[ ! -d "$TARGET" ]]; then
  rm -rf "$TARGET"
  git clone --depth 1 https://github.com/kg-construct/rml-test-cases.git "$TARGET"
  (cd "$TARGET" && git fetch --depth 1 origin "$SUITE_COMMIT" && git checkout "$SUITE_COMMIT")
  echo "$SUITE_COMMIT" > inputs/.suite_commit
fi

if [[ ! -f "$RMLMAPPER_JAR" ]]; then
  echo "fetching rmlmapper-java ${RMLMAPPER_VERSION}..."
  curl -fL --retry 3 -o "$RMLMAPPER_JAR" \
    "https://github.com/RMLio/rmlmapper-java/releases/download/v${RMLMAPPER_VERSION}/rmlmapper-${RMLMAPPER_VERSION}-${RMLMAPPER_BUILD}-all.jar"
fi
# Absolutise — run_suite.py invokes java with cwd=<test_dir>, so a
# relative jar path would resolve against the wrong directory.
RMLMAPPER_JAR="$(realpath "$RMLMAPPER_JAR")"
export RMLMAPPER_JAR

# Morph-KGC is launched per-test via `uv run --isolated`; the spike's own
# venv has uv installed at spikes/venv/bin, but it isn't on PATH by
# default. Prepend it so run_suite.py's subprocess.run(["uv", ...]) works.
export PATH="$(cd .. && pwd)/venv/bin:$PATH"
exec ../.venv/bin/python run_suite.py
