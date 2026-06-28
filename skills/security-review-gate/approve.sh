#!/usr/bin/env bash
# Record a security-review approval receipt for a commit.
#
#   approve.sh <commit-sha> [max_severity]
#
# Run this AFTER `/security-review` when the changes for <commit-sha> have no
# findings at or above the gate threshold. If max_severity is supplied and is at
# or above the threshold (default high), approval is refused. The receipt lets
# the PreToolUse gate allow the matching push/merge.
set -u

usage() { echo "usage: approve.sh <commit-sha> [max_severity]" >&2; }

SELF="$(cd "$(dirname "$0")" && pwd)"
_lib=""
for c in "${GATE_LIB_DIR:-}" "$SELF/lib" "$SELF/../lib"; do
  if [ -n "$c" ] && [ -f "$c/gate.sh" ]; then _lib="$c"; break; fi
done
[ -z "$_lib" ] && { echo "error: cannot locate gate library" >&2; exit 1; }
# shellcheck source=/dev/null
. "$_lib/gate.sh"

SHA="${1:-}"
MAXSEV="${2:-}"
[ -z "$SHA" ] && { usage; exit 2; }

# Validate the commit (accepts a ref or sha); store the full sha as the key.
full="$(git rev-parse --verify -q "${SHA}^{commit}" 2>/dev/null)" \
  || { echo "error: '$SHA' is not a commit in this repository" >&2; exit 1; }

threshold="$(gate_threshold)"
if [ -n "$MAXSEV" ]; then
  sev_should_block "$MAXSEV" "$threshold"
  case $? in
    0) echo "refusing to approve: max_severity '$MAXSEV' is at or above the threshold '$threshold'." >&2
       echo "Fix the findings, re-run /security-review, then approve." >&2
       exit 1 ;;
    2) echo "error: unrecognised severity '$MAXSEV' (use none/low/medium/high/critical)" >&2
       exit 1 ;;
  esac
fi

note="approved sha=$full severity=${MAXSEV:-unspecified} threshold=$threshold"
receipt_record "$full" "$note" || { echo "error: failed to record receipt" >&2; exit 1; }
log_info "event=approved sha=$full severity=${MAXSEV:-unspecified} threshold=$threshold"
echo "Approved $full for push/merge (severity: ${MAXSEV:-unspecified}, threshold: $threshold)."
