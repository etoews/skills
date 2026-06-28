#!/usr/bin/env bash
# Behaviour: the verdict cache stores a review result keyed by commit SHA so
# the same commits are not re-reviewed (coordination between the two hooks and
# cost saving on retried pushes).
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

export GATE_CACHE_DIR="$(mktempdir)"
. "$here/../lib/cache.sh"

sha=0123456789abcdef0123456789abcdef01234567

# A SHA that was never reviewed is a miss (exit 1).
assert_status 1 "$(status_of cache_get "$sha")" "unknown sha is a miss"

# After storing a verdict, the SHA is a hit and the verdict round-trips intact.
verdict='{"max_severity":"high","findings":[{"severity":"high","title":"x"}]}'
cache_put "$sha" "$verdict"
assert_status 0 "$(status_of cache_get "$sha")" "stored sha is a hit"
assert_eq "$verdict" "$(cache_get "$sha")" "verdict round-trips"

# Distinct SHAs are isolated.
assert_status 1 "$(status_of cache_get ffffffffffffffffffffffffffffffffffffffff)" "other sha still a miss"

# The cache dir is created on demand (it did not pre-exist this put).
assert_eq "yes" "$([ -d "$GATE_CACHE_DIR" ] && echo yes)" "cache dir exists after put"
