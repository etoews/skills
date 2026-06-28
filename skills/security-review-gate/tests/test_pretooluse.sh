#!/usr/bin/env bash
# Behaviour: the PreToolUse hook requires a review-approval receipt before an
# in-session `git push` or `git merge` into main. No receipt -> deny with
# instructions; receipt present (or bypass) -> allow; non-gated commands ignored.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"
. "$here/../lib/receipt.sh"

HOOK="$here/../hooks/pretooluse.sh"

make_repo() {
  local d; d="$(mktempdir)"
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@t.test
  git -C "$d" config user.name tester
  echo hi > "$d/f.txt"; git -C "$d" add -A; git -C "$d" commit -q -m init
  git -C "$d" checkout -q -b feature
  echo more >> "$d/f.txt"; git -C "$d" commit -q -am feat
  git -C "$d" checkout -q main
  printf '%s' "$d"
}
mkjson() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
run_pre() { ( cd "$1" && printf '%s' "$2" | GATE_RECEIPT_DIR="$1/.receipts" bash "$HOOK" 2>/dev/null ); }
decision() { printf '%s' "$1" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null; }
reason() { printf '%s' "$1" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null; }
record() { ( cd "$1" && GATE_RECEIPT_DIR="$1/.receipts" bash -c '. "'"$here"'/../lib/receipt.sh"; receipt_record "'"$2"'" "ok"' ); }

repo="$(make_repo)"

# Push with no receipt -> deny with actionable instructions.
out="$(run_pre "$repo" "$(mkjson 'git push origin main')")"
assert_eq deny "$(decision "$out")" "push without receipt is denied"
assert_contains "$(reason "$out")" "/security-review" "deny tells you to run /security-review"
assert_contains "$(reason "$out")" "approve.sh" "deny tells you how to approve"

# Record a receipt for HEAD -> push is allowed (silent).
record "$repo" "$(git -C "$repo" rev-parse HEAD)"
out="$(run_pre "$repo" "$(mkjson 'git push origin main')")"
assert_eq "" "$(decision "$out")" "push with receipt is allowed"
assert_eq "" "$out" "allowed push is silent"

# Merge of a feature branch INTO main with no receipt -> deny.
repo2="$(make_repo)"
out="$(run_pre "$repo2" "$(mkjson 'git merge --ff-only feature')")"
assert_eq deny "$(decision "$out")" "merge into main without receipt is denied"
assert_contains "$(reason "$out")" "merge" "deny mentions the merge context"

# Merge into main WITH a receipt for the feature tip -> allowed.
record "$repo2" "$(git -C "$repo2" rev-parse feature)"
out="$(run_pre "$repo2" "$(mkjson 'git merge --ff-only feature')")"
assert_eq "" "$(decision "$out")" "merge with receipt is allowed"

# Merge while not on main is ignored.
side="$(make_repo)"; git -C "$side" checkout -q feature
out="$(run_pre "$side" "$(mkjson 'git merge --ff-only main')")"
assert_eq "" "$(decision "$out")" "merge off main is not gated"

# Non-gated commands ignored.
assert_eq "" "$(decision "$(run_pre "$repo2" "$(mkjson 'ls -la')")")" "non-git ignored"
assert_eq "" "$(decision "$(run_pre "$repo2" "$(mkjson 'git status')")")" "read-only git ignored"
assert_eq "" "$(decision "$(run_pre "$repo2" "$(mkjson 'git merge-base main feature')")")" "merge-base not a merge"

# Bypass allows without a receipt.
repo3="$(make_repo)"
out="$( cd "$repo3" && printf '%s' "$(mkjson 'git push origin main')" | SKIP_SECURITY_REVIEW=1 GATE_RECEIPT_DIR="$repo3/.receipts" bash "$HOOK" 2>/dev/null )"
assert_eq "" "$(decision "$out")" "bypass allows without receipt"
