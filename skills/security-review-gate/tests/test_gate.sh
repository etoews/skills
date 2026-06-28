#!/usr/bin/env bash
# Behaviour: the gate orchestrator decides allow / block / fail-closed from the
# review verdict, honouring bypass, cache, and the severity threshold, and
# emits structured log events (observability).
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

export CLAUDE_BIN="$here/stubs/claude-stub.sh"
export GATE_CACHE_DIR="$(mktempdir)"
export GATE_LOG_FILE="$(mktempdir)/gate.log"
export GATE_LOG_LEVEL=debug
export STUB_MARKER="$(mktempdir)/calls"   # records whether the review actually ran
. "$here/../lib/gate.sh"

# Capture stdout (the human summary); structured logs land in GATE_LOG_FILE.
gc() { gate_check "$@" 2>/dev/null; }
ran() { [ -s "$STUB_MARKER" ] && echo yes || echo no; }
logs() { cat "$GATE_LOG_FILE" 2>/dev/null; }

# --- bypass --------------------------------------------------------------
rm -f "$STUB_MARKER"
out="$(SKIP_SECURITY_REVIEW=1 gc sha-bypass main..HEAD push)"
assert_status 0 "$?" "bypass allows"
assert_contains "$out" "bypassed" "bypass prints a message"
assert_eq no "$(ran)" "review not run on bypass"

# --- clean review allows and caches --------------------------------------
rm -f "$STUB_MARKER"
out="$(STUB_MAXSEV=none gc sha-clean main..HEAD push)"
assert_status 0 "$?" "clean allows"
assert_contains "$out" "no findings" "clean message"
assert_eq yes "$(ran)" "clean actually ran the review"
assert_status 0 "$(status_of cache_get sha-clean)" "clean verdict cached"

# --- high finding blocks (default threshold = high) ----------------------
out="$(STUB_MAXSEV=high STUB_FINDINGS='[{"severity":"high","title":"SQL injection","location":"db.py:10"}]' gc sha-high main..HEAD 'merge to main')"
assert_status 1 "$?" "high blocks"
assert_contains "$out" "BLOCKED" "block banner"
assert_contains "$out" "SQL injection" "lists the finding"
assert_contains "$out" "no-verify" "block prints override hint"

# --- medium allowed under high threshold, but noted ----------------------
out="$(STUB_MAXSEV=medium STUB_FINDINGS='[{"severity":"medium","title":"weak hash"}]' gc sha-med main..HEAD push)"
assert_status 0 "$?" "medium allowed under high threshold"
assert_contains "$out" "below threshold" "medium noted as below threshold"

# --- lowering threshold blocks the medium finding ------------------------
out="$(SECURITY_REVIEW_THRESHOLD=medium STUB_MAXSEV=medium STUB_FINDINGS='[{"severity":"medium","title":"weak hash"}]' gc sha-med2 main..HEAD push)"
assert_status 1 "$?" "medium blocks at medium threshold"

# --- cache hit reuses verdict and does NOT re-run the review -------------
cache_put sha-cached '{"max_severity":"critical","findings":[{"severity":"critical","title":"rce"}]}'
rm -f "$STUB_MARKER"
out="$(STUB_MAXSEV=none gc sha-cached main..HEAD push)"   # stub says none; cache says critical
assert_status 1 "$?" "cache hit blocks from cached critical"
assert_eq no "$(ran)" "review not re-run on cache hit"

# --- fail-closed paths ---------------------------------------------------
out="$(STUB_EXIT=1 gc sha-err main..HEAD push)"
assert_status 3 "$?" "claude error fails closed"
assert_contains "$out" "COULD NOT COMPLETE" "fail-closed message"

out="$(STUB_EMIT='garbage not json' gc sha-garb main..HEAD push)"
assert_status 3 "$?" "unparseable output fails closed"

out="$(STUB_SUBTYPE=error_max_budget_usd STUB_IS_ERROR=true gc sha-bud main..HEAD push)"
assert_status 3 "$?" "error-subtype envelope fails closed"

# Fail-closed verdicts are not cached, so a later run can retry.
assert_status 1 "$(status_of cache_get sha-err)" "errors are not cached"

# --- observability: structured events were logged ------------------------
assert_contains "$(logs)" "event=blocked" "logs a block event"
assert_contains "$(logs)" "event=allowed" "logs an allow event"
assert_contains "$(logs)" "event=cache_hit" "logs a cache hit"
assert_contains "$(logs)" "level=error" "logs errors for fail-closed"
