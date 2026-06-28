#!/usr/bin/env bash
# Behaviour: review_extract_verdict turns a real `claude -p --output-format json`
# envelope into the validated verdict object, and rejects error/garbage output
# so the gate can fail closed.
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/helpers.sh"
. "$here/../lib/review.sh"

ok='{"type":"result","subtype":"success","is_error":false,"result":"{\"max_severity\":\"high\",\"findings\":[]}","structured_output":{"max_severity":"high","findings":[]}}'

# A successful envelope yields the structured verdict.
v="$(review_extract_verdict "$ok")"
assert_status 0 "$?" "success envelope extracts"
assert_eq high "$(review_max_severity "$v")" "max_severity read from verdict"

# Falls back to the .result string when structured_output is absent.
no_so='{"type":"result","subtype":"success","is_error":false,"result":"{\"max_severity\":\"medium\",\"findings\":[]}"}'
v2="$(review_extract_verdict "$no_so")"
assert_status 0 "$?" "result fallback extracts"
assert_eq medium "$(review_max_severity "$v2")" "max_severity from .result fallback"

# An error envelope is rejected (caller fails closed).
err='{"type":"result","subtype":"error_max_budget_usd","is_error":true,"result":""}'
assert_status 1 "$(status_of review_extract_verdict "$err")" "error subtype rejected"

# is_error true is rejected even if subtype looks ok.
err2='{"type":"result","subtype":"success","is_error":true,"structured_output":{"max_severity":"high","findings":[]}}'
assert_status 1 "$(status_of review_extract_verdict "$err2")" "is_error rejected"

# Non-JSON garbage is rejected.
assert_status 1 "$(status_of review_extract_verdict 'not json at all')" "garbage rejected"

# Empty output is rejected.
assert_status 1 "$(status_of review_extract_verdict '')" "empty rejected"

# A verdict missing max_severity is rejected.
bad='{"type":"result","subtype":"success","is_error":false,"structured_output":{"findings":[]}}'
assert_status 1 "$(status_of review_extract_verdict "$bad")" "missing max_severity rejected"
