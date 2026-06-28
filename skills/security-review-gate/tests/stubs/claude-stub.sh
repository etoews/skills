#!/usr/bin/env bash
# Test double for the `claude` CLI. Ignores all arguments and emits a canned
# `--output-format json` envelope matching the real shape captured during the
# spike. Behaviour is driven entirely by env vars so tests can script outcomes:
#
#   STUB_EMIT       raw stdout override (bypasses envelope construction)
#   STUB_SUBTYPE    default "success"
#   STUB_IS_ERROR   default "false"
#   STUB_MAXSEV     default "none"
#   STUB_FINDINGS   JSON array, default "[]"
#   STUB_EXIT       process exit code, default 0
#   STUB_MARKER     if set, append a line to this file (proves the stub ran)
set -u

[ -n "${STUB_MARKER:-}" ] && printf 'called\n' >> "$STUB_MARKER"

if [ -n "${STUB_EMIT:-}" ]; then
  printf '%s' "$STUB_EMIT"
  exit "${STUB_EXIT:-0}"
fi

sub="${STUB_SUBTYPE:-success}"
iserr="${STUB_IS_ERROR:-false}"
maxsev="${STUB_MAXSEV:-none}"
findings="${STUB_FINDINGS:-[]}"
verdict="$(printf '{"max_severity":"%s","findings":%s}' "$maxsev" "$findings")"

printf '{"type":"result","subtype":"%s","is_error":%s,"result":%s,"structured_output":%s}\n' \
  "$sub" "$iserr" "$(printf '%s' "$verdict" | jq -Rs .)" "$verdict"

exit "${STUB_EXIT:-0}"
