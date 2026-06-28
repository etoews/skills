#!/usr/bin/env bash
# Minimal assertion helpers for the security-review-gate test suite.
#
# Source this at the top of a test file. Each test file is executed as its own
# process by run.sh and exits nonzero if any assertion failed. Keeping the
# harness dependency-free (no bats) means contributors can run the suite with
# nothing but bash.

ASSERT_COUNT=0
FAIL_COUNT=0
_CLEANUP=()

# register_cleanup <path> : remove this path when the test process exits.
register_cleanup() { _CLEANUP+=("$1"); }

# mktempdir : create a temp dir, register it for cleanup, print its path.
mktempdir() { local d; d="$(mktemp -d)"; register_cleanup "$d"; printf '%s' "$d"; }

_ok()  { ASSERT_COUNT=$((ASSERT_COUNT + 1)); }
_bad() { ASSERT_COUNT=$((ASSERT_COUNT + 1)); FAIL_COUNT=$((FAIL_COUNT + 1)); printf '    x %s\n' "$1" >&2; }

assert_eq() { # expected actual [label]
  if [ "$1" = "$2" ]; then _ok; else _bad "${3:-assert_eq}: expected [$1], got [$2]"; fi
}

assert_status() { # expected actual [label]
  if [ "$1" = "$2" ]; then _ok; else _bad "${3:-assert_status}: expected exit [$1], got [$2]"; fi
}

assert_contains() { # haystack needle [label]
  case "$1" in
    *"$2"*) _ok ;;
    *) _bad "${3:-assert_contains}: [$1] does not contain [$2]" ;;
  esac
}

assert_not_contains() { # haystack needle [label]
  case "$1" in
    *"$2"*) _bad "${3:-assert_not_contains}: [$1] unexpectedly contains [$2]" ;;
    *) _ok ;;
  esac
}

# Run a command, swallow its output, and print its exit status. Lets a test
# assert on exit codes without set -e aborting the test body.
status_of() { "$@" >/dev/null 2>&1; printf '%s' "$?"; }

_report() {
  local rc=$? p
  for p in "${_CLEANUP[@]:-}"; do [ -n "$p" ] && rm -rf "$p"; done
  if [ "$FAIL_COUNT" -gt 0 ]; then
    printf '    %d/%d assertions failed\n' "$FAIL_COUNT" "$ASSERT_COUNT" >&2
    exit 1
  fi
  [ "$rc" -ne 0 ] && exit "$rc"
  exit 0
}
trap _report EXIT
