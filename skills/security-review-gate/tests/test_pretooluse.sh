#!/usr/bin/env bash
# Behaviour: the PreToolUse hook gates in-session `git push` and `git merge`
# into main, emitting a permissionDecision=deny on block/fail-closed and staying
# silent (allow normal flow) otherwise or for non-gated commands.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

HOOK="$here/../hooks/pretooluse.sh"
export CLAUDE_BIN="$here/stubs/claude-stub.sh"

make_repo() {
  local d; d="$(mktempdir)"
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@t.test
  git -C "$d" config user.name tester
  echo hi > "$d/f.txt"; git -C "$d" add -A; git -C "$d" commit -q -m init
  # a feature branch with an extra commit, for merge tests
  git -C "$d" checkout -q -b feature
  echo more >> "$d/f.txt"; git -C "$d" commit -q -am feat
  git -C "$d" checkout -q main
  printf '%s' "$d"
}

mkjson() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
run_pre() { ( cd "$1" && printf '%s' "$2" | GATE_CACHE_DIR="$1/.cache" bash "$HOOK" 2>/dev/null ); }
decision() { printf '%s' "$1" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null; }

repo="$(make_repo)"

# A push with a high finding is denied.
out="$(STUB_MAXSEV=high STUB_FINDINGS='[{"severity":"high","title":"xss"}]' run_pre "$repo" "$(mkjson 'git push origin main')")"
assert_eq deny "$(decision "$out")" "push with high finding is denied"

# A push with a clean review is silent (allow normal flow).
# Fresh repo: a distinct commit SHA, so no verdict is cached from above.
repo_clean="$(make_repo)"
out="$(STUB_MAXSEV=none run_pre "$repo_clean" "$(mkjson 'git push origin main')")"
assert_eq "" "$(decision "$out")" "clean push is not denied"
assert_eq "" "$out" "clean push produces no output"

# A merge of a feature branch INTO main with a high finding is denied.
out="$(STUB_MAXSEV=critical STUB_FINDINGS='[{"severity":"critical","title":"rce"}]' run_pre "$repo" "$(mkjson 'git merge --ff-only feature')")"
assert_eq deny "$(decision "$out")" "merge into main with critical finding is denied"

# A merge while NOT on main is ignored (push backstop will catch it later).
side="$(make_repo)"; git -C "$side" checkout -q feature
out="$(STUB_MAXSEV=high run_pre "$side" "$(mkjson 'git merge --ff-only main')")"
assert_eq "" "$(decision "$out")" "merge off main is not gated here"

# Non-gated commands are ignored.
out="$(STUB_MAXSEV=high run_pre "$repo" "$(mkjson 'ls -la')")"
assert_eq "" "$(decision "$out")" "non-git command ignored"
out="$(STUB_MAXSEV=high run_pre "$repo" "$(mkjson 'git status')")"
assert_eq "" "$(decision "$out")" "read-only git ignored"

# `git merge-base` must NOT be mistaken for a merge.
out="$(STUB_MAXSEV=high run_pre "$repo" "$(mkjson 'git merge-base main feature')")"
assert_eq "" "$(decision "$out")" "merge-base is not a merge"

# Fail-closed: a review error denies the push (fresh repo so nothing is cached).
repo_err="$(make_repo)"
out="$(STUB_EXIT=1 run_pre "$repo_err" "$(mkjson 'git push origin main')")"
assert_eq deny "$(decision "$out")" "review error denies the push"
assert_contains "$out" "COULD NOT COMPLETE" "fail-closed reason surfaced"
