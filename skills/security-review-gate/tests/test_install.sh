#!/usr/bin/env bash
# Behaviour: install.sh wires the gate into a target repo (copies scripts, sets
# core.hooksPath, merges the PreToolUse hook into .claude/settings.json),
# idempotently; uninstall.sh reverses it cleanly. The installed pre-push hook
# resolves its library and blocks on high findings.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

INSTALL="$here/../install.sh"
UNINSTALL="$here/../uninstall.sh"
export CLAUDE_BIN="$here/stubs/claude-stub.sh"
ZERO=0000000000000000000000000000000000000000

make_repo() {
  local d; d="$(mktempdir)"
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@t.test
  git -C "$d" config user.name tester
  echo hi > "$d/f.txt"; git -C "$d" add -A; git -C "$d" commit -q -m init
  printf '%s' "$d"
}
pt_count() { # count our PreToolUse matcher entries in settings
  jq '[.hooks.PreToolUse[]? | select(any(.hooks[]?; .command | test("security-review-gate/pretooluse.sh")))] | length' \
    "$1/.claude/settings.json" 2>/dev/null
}

repo="$(make_repo)"
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_status 0 "$?" "install succeeds"
assert_eq yes "$([ -x "$repo/.security-review-gate/githooks/pre-push" ] && echo yes)" "pre-push installed and executable"
assert_eq yes "$([ -f "$repo/.security-review-gate/lib/gate.sh" ] && echo yes)" "library copied"
assert_eq ".security-review-gate/githooks" "$(git -C "$repo" config --local core.hooksPath)" "core.hooksPath set"

# Settings gained exactly one of our PreToolUse entries.
assert_eq 1 "$(pt_count "$repo")" "one PreToolUse entry after install"

# Re-installing is idempotent (no duplicate entries, still works).
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_eq 1 "$(pt_count "$repo")" "still one PreToolUse entry after reinstall"

# A foreign setting is preserved across install.
jq '.env = {"FOO":"bar"}' "$repo/.claude/settings.json" > "$repo/.claude/s.tmp" && mv "$repo/.claude/s.tmp" "$repo/.claude/settings.json"
bash "$INSTALL" "$repo" >/dev/null 2>&1
assert_eq bar "$(jq -r '.env.FOO' "$repo/.claude/settings.json")" "foreign settings preserved"
assert_eq 1 "$(pt_count "$repo")" "still one entry after reinstall over foreign settings"

# The INSTALLED pre-push hook resolves its library and blocks a high finding.
sha="$(git -C "$repo" rev-parse HEAD)"
out="$( cd "$repo" && printf 'refs/heads/main %s refs/heads/main %s\n' "$sha" "$ZERO" \
        | STUB_MAXSEV=high GATE_CACHE_DIR="$repo/.cache" bash "$repo/.security-review-gate/githooks/pre-push" origin url 2>/dev/null )"
assert_status 1 "$?" "installed pre-push blocks high finding"
assert_contains "$out" "BLOCKED" "installed hook prints summary"

# Foreign core.hooksPath is not clobbered.
repo_hp="$(make_repo)"
git -C "$repo_hp" config --local core.hooksPath ".my-hooks"
bash "$INSTALL" "$repo_hp" >/dev/null 2>&1
assert_status 1 "$?" "install refuses to overwrite foreign hooksPath"
assert_eq ".my-hooks" "$(git -C "$repo_hp" config --local core.hooksPath)" "foreign hooksPath untouched"
assert_eq no "$([ -d "$repo_hp/.security-review-gate" ] && echo yes || echo no)" "no files written on refusal"

# Uninstall reverses everything.
bash "$UNINSTALL" "$repo" >/dev/null 2>&1
assert_status 0 "$?" "uninstall succeeds"
assert_eq no "$([ -d "$repo/.security-review-gate" ] && echo yes || echo no)" "gate dir removed"
assert_eq "" "$(git -C "$repo" config --local core.hooksPath || true)" "core.hooksPath unset"
assert_eq 0 "$(pt_count "$repo")" "no PreToolUse entries after uninstall"
assert_eq bar "$(jq -r '.env.FOO' "$repo/.claude/settings.json")" "foreign settings still preserved after uninstall"
