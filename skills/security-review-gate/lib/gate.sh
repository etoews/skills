#!/usr/bin/env bash
# Gate orchestrator: the shared brain both hooks call.
#
# gate_check <tip_sha> <range> <context>
#   tip_sha : commit SHA being introduced (cache key)
#   range   : git range to review (e.g. main..HEAD)
#   context : human label for messages (e.g. "push", "merge to main")
#
# Returns: 0 allow, 1 block (findings at/above threshold), 3 fail-closed
#          (could not obtain a trustworthy verdict). Prints a human-readable
#          summary to stdout; structured events go to the log (stderr/file).
#
# Config (env): SKIP_SECURITY_REVIEW, SECURITY_REVIEW_THRESHOLD (default high),
#               plus the review.sh knobs (model, cost cap, tools, prompt).

_gate_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "$_gate_dir/log.sh"
. "$_gate_dir/severity.sh"
. "$_gate_dir/cache.sh"
. "$_gate_dir/review.sh"

_gate_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;; *) return 1 ;;
  esac
}

_gate_bypass_hint() {
  printf 'Override (use sparingly): set SKIP_SECURITY_REVIEW=1, or for a push add `--no-verify`.\n'
}

_gate_findings_list() { # <verdict_json>
  printf '%s' "$1" | jq -r '.findings[]? | "  [\(.severity)] \(.title)" + (if .location then " (\(.location))" else "" end)' 2>/dev/null
}

_gate_block_summary() { # <context> <max> <threshold> <verdict>
  printf 'SECURITY REVIEW BLOCKED this %s.\n' "$1"
  printf 'Highest severity: %s (block threshold: %s).\n' "$2" "$3"
  local list; list="$(_gate_findings_list "$4")"
  [ -n "$list" ] && printf 'Findings:\n%s\n' "$list"
  _gate_bypass_hint
}

_gate_allow_summary() { # <context> <max> <verdict>
  if [ "$(sev_rank "$2" 2>/dev/null || echo 0)" -gt 0 ]; then
    printf 'security-review-gate: %s allowed; %s-severity findings noted (below threshold):\n' "$1" "$2"
    _gate_findings_list "$3"
  else
    printf 'security-review-gate: %s allowed; no findings.\n' "$1"
  fi
}

_gate_fail_closed() { # <context> <reason>
  printf 'SECURITY REVIEW COULD NOT COMPLETE for this %s: %s.\n' "$1" "$2"
  printf 'Failing closed (blocking) by design.\n'
  _gate_bypass_hint
}

gate_check() {
  local sha="$1" range="$2" context="${3:-change}"
  local threshold="${SECURITY_REVIEW_THRESHOLD:-high}"

  if _gate_truthy "${SKIP_SECURITY_REVIEW:-}"; then
    log_warn "event=bypass context=$context sha=$sha reason=SKIP_SECURITY_REVIEW"
    printf 'security-review-gate: bypassed via SKIP_SECURITY_REVIEW for this %s.\n' "$context"
    return 0
  fi

  local verdict source
  if verdict="$(cache_get "$sha" 2>/dev/null)"; then
    source=cache
    log_info "event=cache_hit context=$context sha=$sha"
  else
    source=review
    log_info "event=review_start context=$context sha=$sha range=$range threshold=$threshold"
    local raw rc
    raw="$(review_run "$range")"; rc=$?
    if [ "$rc" -ne 0 ]; then
      log_error "event=review_error context=$context sha=$sha claude_exit=$rc"
      _gate_fail_closed "$context" "the review process exited with status $rc"
      return 3
    fi
    if ! verdict="$(review_extract_verdict "$raw")"; then
      log_error "event=verdict_unparseable context=$context sha=$sha"
      _gate_fail_closed "$context" "the review did not return a parseable verdict"
      return 3
    fi
    cache_put "$sha" "$verdict" || log_warn "event=cache_write_failed context=$context sha=$sha"
  fi

  local max; max="$(review_max_severity "$verdict")"
  sev_should_block "$max" "$threshold"
  case $? in
    0)
      log_warn "event=blocked context=$context sha=$sha max_severity=$max threshold=$threshold source=$source"
      _gate_block_summary "$context" "$max" "$threshold" "$verdict"
      return 1 ;;
    1)
      log_info "event=allowed context=$context sha=$sha max_severity=$max threshold=$threshold source=$source"
      _gate_allow_summary "$context" "$max" "$verdict"
      return 0 ;;
    *)
      log_error "event=bad_severity context=$context sha=$sha max_severity=$max"
      _gate_fail_closed "$context" "the review returned an unrecognised severity '$max'"
      return 3 ;;
  esac
}
