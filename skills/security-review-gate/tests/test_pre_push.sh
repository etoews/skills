#!/usr/bin/env bash
# Behaviour: the git pre-push hook reviews the commits being pushed and aborts
# the push (nonzero exit) on high/critical findings.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

HOOK="$here/../hooks/pre-push"
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

# push a ref update through the hook; echoes exit status as last line of stderr
push_through() { # repo stdin_line
  local repo="$1" line="$2"
  ( cd "$repo" && printf '%s\n' "$line" | GATE_CACHE_DIR="$repo/.cache" bash "$HOOK" origin https://example/repo.git )
}

repo="$(make_repo)"
sha="$(git -C "$repo" rev-parse HEAD)"

# A high finding aborts the push.
out="$(STUB_MAXSEV=high STUB_FINDINGS='[{"severity":"high","title":"hardcoded secret"}]' push_through "$repo" "refs/heads/main $sha refs/heads/main $ZERO" 2>/dev/null)"
assert_status 1 "$?" "high finding aborts push"
assert_contains "$out" "BLOCKED" "push abort prints summary"

# A clean review lets the push proceed.
repo2="$(make_repo)"; sha2="$(git -C "$repo2" rev-parse HEAD)"
STUB_MAXSEV=none push_through "$repo2" "refs/heads/main $sha2 refs/heads/main $ZERO" >/dev/null 2>&1
assert_status 0 "$?" "clean review allows push"

# A branch deletion is a no-op: nothing to review, push allowed, review not run.
repo3="$(make_repo)"; export STUB_MARKER="$(mktempdir)/calls3"
STUB_MAXSEV=high push_through "$repo3" "(delete) $ZERO refs/heads/dead $sha" >/dev/null 2>&1
assert_status 0 "$?" "branch deletion allowed"
assert_eq no "$([ -s "$STUB_MARKER" ] && echo yes || echo no)" "deletion does not run a review"
unset STUB_MARKER

# Bypass env lets the push through without review.
repo4="$(make_repo)"; sha4="$(git -C "$repo4" rev-parse HEAD)"; export STUB_MARKER="$(mktempdir)/calls4"
SKIP_SECURITY_REVIEW=1 STUB_MAXSEV=high push_through "$repo4" "refs/heads/main $sha4 refs/heads/main $ZERO" >/dev/null 2>&1
assert_status 0 "$?" "bypass allows push"
assert_eq no "$([ -s "$STUB_MARKER" ] && echo yes || echo no)" "bypass does not run a review"
unset STUB_MARKER
