#!/usr/bin/env bash
# Behaviour: approval receipts record that a security review was approved for a
# specific commit SHA, so the gate can let that commit through.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"

export GATE_RECEIPT_DIR="$(mktempdir)"
. "$here/../lib/receipt.sh"

sha=0123456789abcdef0123456789abcdef01234567

# No receipt yet -> miss.
assert_status 1 "$(status_of receipt_exists "$sha")" "unknown sha has no receipt"

# After recording, the receipt exists and its note round-trips.
receipt_record "$sha" "approved: max_severity=none"
assert_status 0 "$(status_of receipt_exists "$sha")" "recorded sha has a receipt"
assert_contains "$(receipt_get "$sha")" "max_severity=none" "receipt note round-trips"

# Distinct SHAs are isolated.
assert_status 1 "$(status_of receipt_exists ffffffffffffffffffffffffffffffffffffffff)" "other sha still a miss"

# The receipt dir is created on demand.
assert_eq yes "$([ -d "$GATE_RECEIPT_DIR" ] && echo yes)" "receipt dir created"
