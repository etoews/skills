#!/usr/bin/env bash
# Behaviour: install.sh copies the gate scripts and merges the PreToolUse hook
# into .claude/settings.json (idempotently, preserving foreign settings); the
# installed hook denies a push without a receipt and allows it with one;
# uninstall.sh reverses everything.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"
. "$here/../lib/receipt.sh"

INSTALL="$here/../install.sh"
UNINSTALL="$here/../uninstall.sh"

make_repo() {
  local d; d="$(mktempdir)"
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@t.test
  git -C "$d" config user.name tester
  echo hi > "$d/f.txt"; git -C "$d" add -A; git -C "$d" commit -q -m init
  printf '%s' "$d"
}
pt_count() {
  jq '[.hooks.PreToolUse[]? | select(any(.hooks[]?; .command | test("security-review-gate/pretooluse.sh")))] | length' \
    "$1/.claude/settings.json" 2>/dev/null
}
mkjson() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }

repo="$(make_repo)"
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_status 0 "$?" "install succeeds"
assert_eq yes "$([ -x "$repo/.security-review-gate/pretooluse.sh" ] && echo yes)" "pretooluse installed and executable"
assert_eq yes "$([ -x "$repo/.security-review-gate/approve.sh" ] && echo yes)" "approve installed and executable"
assert_eq yes "$([ -f "$repo/.security-review-gate/lib/gate.sh" ] && echo yes)" "library copied"
assert_eq 1 "$(pt_count "$repo")" "one PreToolUse entry after install"

# No git hook is wired (in-session only).
assert_eq "" "$(git -C "$repo" config --local core.hooksPath || true)" "no core.hooksPath set"

# Idempotent reinstall.
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_eq 1 "$(pt_count "$repo")" "still one entry after reinstall"

# Foreign settings preserved.
jq '.env = {"FOO":"bar"}' "$repo/.claude/settings.json" > "$repo/.claude/s.tmp" && mv "$repo/.claude/s.tmp" "$repo/.claude/settings.json"
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_eq bar "$(jq -r '.env.FOO' "$repo/.claude/settings.json")" "foreign settings preserved"
assert_eq 1 "$(pt_count "$repo")" "still one entry after reinstall over foreign settings"

# The INSTALLED hook resolves its lib and denies a push with no receipt.
HOOK="$repo/.security-review-gate/pretooluse.sh"
out="$( cd "$repo" && printf '%s' "$(mkjson 'git push origin main')" | GATE_RECEIPT_DIR="$repo/.rcpt" bash "$HOOK" 2>/dev/null )"
assert_eq deny "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty')" "installed hook denies without receipt"
assert_contains "$out" ".security-review-gate/approve.sh" "deny references the installed approve.sh"

# With a receipt for HEAD, the installed hook allows.
GATE_RECEIPT_DIR="$repo/.rcpt" bash -c '. "'"$here"'/../lib/receipt.sh"; receipt_record "'"$(git -C "$repo" rev-parse HEAD)"'" ok'
out="$( cd "$repo" && printf '%s' "$(mkjson 'git push origin main')" | GATE_RECEIPT_DIR="$repo/.rcpt" bash "$HOOK" 2>/dev/null )"
assert_eq "" "$out" "installed hook allows with receipt"

# Uninstall reverses everything.
bash "$UNINSTALL" "$repo" >/dev/null 2>&1
assert_status 0 "$?" "uninstall succeeds"
assert_eq no "$([ -d "$repo/.security-review-gate" ] && echo yes || echo no)" "gate dir removed"
assert_eq 0 "$(pt_count "$repo")" "no PreToolUse entries after uninstall"
assert_eq bar "$(jq -r '.env.FOO' "$repo/.claude/settings.json")" "foreign settings preserved after uninstall"
