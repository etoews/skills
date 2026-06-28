#!/usr/bin/env bash
# Behaviour: approve.sh records an approval receipt for a commit, but refuses
# when told the review found something at or above the threshold (or an
# unrecognised severity / unknown commit).
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"
. "$here/../lib/receipt.sh"

APPROVE="$here/../approve.sh"

repo="$(mktempdir)"
git -C "$repo" init -q -b main
git -C "$repo" config user.email t@t.test
git -C "$repo" config user.name tester
echo a > "$repo/f.txt"; git -C "$repo" add -A; git -C "$repo" commit -q -m c1
echo b >> "$repo/f.txt"; git -C "$repo" commit -q -am c2
export GATE_RECEIPT_DIR="$repo/.receipts"
sha1="$(git -C "$repo" rev-parse HEAD~1)"
sha2="$(git -C "$repo" rev-parse HEAD)"

approve() { ( cd "$repo" && bash "$APPROVE" "$@" ); }

# Clean approval (no severity) records a receipt.
approve "$sha1" >/dev/null 2>&1
assert_status 0 "$?" "clean approval succeeds"
assert_status 0 "$(status_of receipt_exists "$sha1")" "receipt recorded for sha1"

# A severity below threshold (default high) is approved.
approve "$sha2" medium >/dev/null 2>&1
assert_status 0 "$?" "medium approval succeeds under high threshold"
assert_status 0 "$(status_of receipt_exists "$sha2")" "receipt recorded for sha2"

# A severity at/above threshold is refused and records nothing.
sha_unrev="$(git -C "$repo" rev-parse HEAD~1)"   # reuse a real commit with its receipt removed
rm -f "$GATE_RECEIPT_DIR/$sha_unrev"
approve "$sha_unrev" high >/dev/null 2>&1
assert_status 1 "$?" "high severity refused"
assert_status 1 "$(status_of receipt_exists "$sha_unrev")" "no receipt when refused"

# An unrecognised severity is an error (cannot validate -> refuse).
approve "$sha_unrev" bogus >/dev/null 2>&1
assert_status 1 "$?" "unrecognised severity errors"

# An unknown commit is an error.
approve 0000000000000000000000000000000000000000 >/dev/null 2>&1
assert_status 1 "$?" "unknown commit errors"

# No args is a usage error.
approve >/dev/null 2>&1
assert_status 2 "$?" "missing sha is a usage error"
