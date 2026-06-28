#!/usr/bin/env bash
# Shared library for the in-session security-review gate.
#
# Sources the leaf modules and exposes small helpers used by the PreToolUse hook
# and approve.sh. Sourced by bash scripts, so ${BASH_SOURCE[0]} resolves the
# sibling modules reliably.

_gate_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "$_gate_dir/log.sh"
. "$_gate_dir/severity.sh"
. "$_gate_dir/receipt.sh"

# gate_truthy <value> : 0 if the value is a truthy string (1/true/yes/on).
gate_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;; *) return 1 ;;
  esac
}

# gate_threshold : the severity at/above which review approval is required.
gate_threshold() { printf '%s' "${SECURITY_REVIEW_THRESHOLD:-high}"; }
