#!/usr/bin/env bash
# Structured logging to stderr (and an optional file) for observability.
#
# Lines look like:  security-review-gate level=info event=allowed sha=...
# so they are greppable and parseable. Levels: debug < info < warn < error.
# Honour $GATE_LOG_LEVEL (default info) and optional $GATE_LOG_FILE.

_log_rank() {
  case "$1" in
    debug) printf 0 ;; info) printf 1 ;; warn) printf 2 ;; error) printf 3 ;;
    *) printf 1 ;;
  esac
}

_log() {
  local lvl="$1"; shift
  [ "$(_log_rank "$lvl")" -lt "$(_log_rank "${GATE_LOG_LEVEL:-info}")" ] && return 0
  local line
  line="$(printf 'security-review-gate level=%s %s' "$lvl" "$*")"
  printf '%s\n' "$line" >&2
  [ -n "${GATE_LOG_FILE:-}" ] && printf '%s\n' "$line" >> "$GATE_LOG_FILE"
  return 0
}

log_debug() { _log debug "$@"; }
log_info()  { _log info "$@"; }
log_warn()  { _log warn "$@"; }
log_error() { _log error "$@"; }
