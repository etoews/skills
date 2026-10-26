#!/usr/bin/env bash
# End-to-end pipeline smoke test: real Phoenix (Docker) + offline stubs (no key).
# Proves the full path - dataset -> experiment -> evaluators -> results - and
# asserts the 3 example cases score on all 3 metrics.
set -euo pipefail
cd "$(dirname "$0")/.."

api_ready() {
  uv run python -c "from phoenix.client import Client; Client(base_url='http://localhost:6006').datasets.list()" >/dev/null 2>&1
}

started_docker=
if api_ready; then
  echo "[e2e] reusing the Phoenix already running on :6006"
else
  echo "[e2e] starting Phoenix via docker compose ..."
  docker compose up -d
  started_docker=1
fi

echo "[e2e] waiting for the Phoenix API ..."
ready=
for _ in $(seq 1 40); do
  if api_ready; then ready=1; break; fi
  sleep 2
done
if [ -z "$ready" ]; then
  echo "[e2e] Phoenix API never became ready"
  [ -n "$started_docker" ] && docker compose logs --tail 40 phoenix
  exit 1
fi

echo "[e2e] running offline eval against the 3 example cases ..."
out="$(uv run python scripts/run_eval.py \
  --dataset datasets/example \
  --model anthropic/claude-opus-4-8 --effort xhigh --offline \
  --experiment-name e2e-offline --dataset-name e2e-example 2>&1)"
echo "$out"

echo "[e2e] asserting results ..."
fail=0
echo "$out" | grep -q "(3 cases)" || { echo "FAIL: expected 3 cases"; fail=1; }
for m in correctness relevance faithfulness; do
  echo "$out" | grep -qE " ${m}[[:space:]]+mean=" || { echo "FAIL: missing metric ${m}"; fail=1; }
done
if [ "$fail" -ne 0 ]; then echo "[e2e] FAILED"; exit 1; fi
echo "[e2e] PASS - open http://localhost:6006 to see the experiment"
