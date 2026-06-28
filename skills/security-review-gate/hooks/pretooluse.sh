#!/usr/bin/env bash
# Claude Code PreToolUse hook — the primary, in-session gate.
#
# Fires before a Bash tool call. If the command is a `git push` or a `git merge`
# into main/master, it runs the security review and, on a block or fail-closed
# verdict, returns permissionDecision=deny so Claude stops and surfaces the
# findings. For non-gated commands (or a clean verdict) it stays silent and lets
# the normal flow proceed.
#
# Reads the hook payload as JSON on stdin; writes a decision object to stdout.
set -u

# Locate the gate library relative to this script (in-repo for tests, or under
# .security-review-gate/ once installed).
_self="$(cd "$(dirname "$0")" && pwd)"
_lib=""
for _c in "${GATE_LIB_DIR:-}" "$_self/lib" "$_self/../lib" "$_self/../../lib"; do
  if [ -n "$_c" ] && [ -f "$_c/gate.sh" ]; then _lib="$_c"; break; fi
done
# Never wedge the session: if we cannot load, allow normal flow (the git
# pre-push hook is the enforcing backstop).
[ -z "$_lib" ] && exit 0
# shellcheck source=/dev/null
. "$_lib/gate.sh"

_payload="$(cat)"
cmd="$(printf '%s' "$_payload" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

_is_push()  { printf '%s' "$cmd" | grep -Eq '(^|[;&|(]|[[:space:]])git[[:space:]]+push([[:space:]]|$)'; }
_is_merge() { printf '%s' "$cmd" | grep -Eq '(^|[;&|(]|[[:space:]])git[[:space:]]+merge([[:space:]]|$)'; }

# First non-option token after the 'merge' subcommand (the source ref).
_merge_source() {
  local rest tok
  rest="${cmd#*merge}"
  for tok in $rest; do
    case "$tok" in
      -*) continue ;;
      *) printf '%s' "$tok"; return 0 ;;
    esac
  done
  return 1
}

# Range describing what an in-session push would send.
_push_range() {
  local up b base
  if up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" && [ -n "$up" ]; then
    printf '%s..HEAD' "$up"; return
  fi
  for b in main master; do
    if git rev-parse --verify -q "refs/heads/$b" >/dev/null 2>&1 \
       && [ "$(git rev-parse "$b")" != "$(git rev-parse HEAD)" ]; then
      base="$(git merge-base "$b" HEAD 2>/dev/null)" && { printf '%s..HEAD' "$base"; return; }
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
  case "$current" in
    main|master) ;;
    *) exit 0 ;;                       # only gate merges INTO main/master
  esac
  source_ref="$(_merge_source)" || exit 0
  sha="$(git rev-parse --verify -q "$source_ref" 2>/dev/null)" || exit 0
  range="HEAD..$source_ref"
  context="merge to $current"
else
  exit 0                               # not a gated command
fi

summary="$(gate_check "$sha" "$range" "$context")"
rc=$?

if [ "$rc" -eq 0 ]; then
  exit 0                               # allow: stay out of the normal flow
fi

# Block (1) or fail-closed (3): deny the tool call with the summary as reason.
jq -n --arg r "$summary" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
