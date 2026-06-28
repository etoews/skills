#!/usr/bin/env bash
# Claude Code PreToolUse hook — the in-session security-review gate.
#
# Before Claude runs `git push` or `git merge` into main/master, require an
# approval receipt for the commit being introduced. If a receipt exists, allow;
# otherwise deny and tell Claude to run `/security-review` and, once clean,
# record approval with approve.sh. Bypass with SKIP_SECURITY_REVIEW=1.
#
# Reads the hook payload as JSON on stdin; writes a decision object to stdout.
set -u

_self="$(cd "$(dirname "$0")" && pwd)"

# Locate the gate library (in-repo for tests, or under .security-review-gate/).
_lib=""
for _c in "${GATE_LIB_DIR:-}" "$_self/lib" "$_self/../lib"; do
  if [ -n "$_c" ] && [ -f "$_c/gate.sh" ]; then _lib="$_c"; break; fi
done
# Never wedge the session: if we cannot load, allow.
[ -z "$_lib" ] && exit 0
# shellcheck source=/dev/null
. "$_lib/gate.sh"

# Resolve approve.sh to an absolute path for the instructions.
_approve="approve.sh"
for _c in "$_self/approve.sh" "$_self/../approve.sh"; do
  [ -f "$_c" ] && { _approve="$(cd "$(dirname "$_c")" && printf '%s/approve.sh' "$PWD")"; break; }
done

cmd="$(cat | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

_is_push()  { printf '%s' "$cmd" | grep -Eq '(^|[;&|(]|[[:space:]])git[[:space:]]+push([[:space:]]|$)'; }
_is_merge() { printf '%s' "$cmd" | grep -Eq '(^|[;&|(]|[[:space:]])git[[:space:]]+merge([[:space:]]|$)'; }

# First non-option token after the 'merge' subcommand (the source ref).
_merge_source() {
  local rest tok
  rest="${cmd#*merge}"
  for tok in $rest; do
    case "$tok" in -*) continue ;; *) printf '%s' "$tok"; return 0 ;; esac
  done
  return 1
}

# Range describing what an in-session push would send (for the review).
_push_range() {
  local up b
  if up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" && [ -n "$up" ]; then
    printf '%s..HEAD' "$up"; return
  fi
  for b in main master; do
    if git rev-parse --verify -q "refs/heads/$b" >/dev/null 2>&1 \
       && [ "$(git rev-parse "$b")" != "$(git rev-parse HEAD)" ]; then
      printf '%s..HEAD' "$b"; return
    fi
  done
  printf 'HEAD'
}

sha=""; range=""; context=""
if _is_push; then
  sha="$(git rev-parse HEAD 2>/dev/null)" || exit 0
  range="$(_push_range)"
  context="push"
elif _is_merge; then
  current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  case "$current" in main|master) ;; *) exit 0 ;; esac   # only gate merges INTO main/master
  src="$(_merge_source)" || exit 0
  sha="$(git rev-parse --verify -q "$src" 2>/dev/null)" || exit 0
  range="HEAD..$src"
  context="merge into $current"
else
  exit 0
fi

if gate_truthy "${SKIP_SECURITY_REVIEW:-}"; then
  log_warn "event=bypass context=$context sha=$sha reason=SKIP_SECURITY_REVIEW"
  exit 0
fi

if receipt_exists "$sha"; then
  log_info "event=allow context=$context sha=$sha reason=receipt"
  exit 0
fi

threshold="$(gate_threshold)"
log_warn "event=deny context=$context sha=$sha threshold=$threshold reason=no_receipt"
reason="$(printf 'Security review required before this %s.\n\nRun `/security-review` in this session and review the changes in %s. If there are NO findings at or above %s severity, record approval and retry:\n\n  bash "%s" %s\n\nIf there are findings at or above %s, fix them first, then review again.' \
  "$context" "$range" "$threshold" "$_approve" "$sha" "$threshold")"

jq -n --arg r "$reason" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
