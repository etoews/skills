#!/usr/bin/env bash
# Behaviour: severity threshold decides whether the gate blocks.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"
. "$here/../lib/severity.sh"

# A high finding against a high threshold blocks (exit 0 = block).
assert_status 0 "$(status_of sev_should_block high high)" "high vs high blocks"

# Below threshold allows (exit 1 = allow).
assert_status 1 "$(status_of sev_should_block medium high)" "medium vs high allows"
assert_status 1 "$(status_of sev_should_block low high)" "low vs high allows"
assert_status 1 "$(status_of sev_should_block none high)" "none vs high allows"

# At or above threshold blocks.
assert_status 0 "$(status_of sev_should_block critical high)" "critical vs high blocks"
assert_status 0 "$(status_of sev_should_block medium medium)" "medium vs medium blocks"

# A stricter threshold blocks lower findings.
assert_status 0 "$(status_of sev_should_block medium low)" "medium vs low blocks"

# Case-insensitive.
assert_status 0 "$(status_of sev_should_block HIGH High)" "case-insensitive blocks"

# Unrecognised severity or threshold is an error (exit 2) -> caller fails closed.
assert_status 2 "$(status_of sev_should_block bogus high)" "unknown severity errors"
assert_status 2 "$(status_of sev_should_block high bogus)" "unknown threshold errors"
assert_status 2 "$(status_of sev_should_block '' high)" "empty severity errors"

# Ranks are ordered.
assert_eq 4 "$(sev_rank critical)" "critical rank"
assert_eq 0 "$(sev_rank none)" "none rank"
