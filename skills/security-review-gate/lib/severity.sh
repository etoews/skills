#!/usr/bin/env bash
# Severity ranking and the block/allow decision. Pure functions, no side
# effects, no external processes — trivially unit-testable.

# sev_rank <level>
#   Print the integer rank of a severity level on stdout.
#   Return 1 (and print nothing) for an unrecognised level.
sev_rank() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    none|clean|info|informational) printf '0' ;;
    low)                           printf '1' ;;
    medium|moderate)               printf '2' ;;
    high)                          printf '3' ;;
    critical)                      printf '4' ;;
    *) return 1 ;;
  esac
}

# sev_should_block <max_severity> <threshold>
#   exit 0 = block, 1 = allow, 2 = error (unrecognised severity/threshold).
sev_should_block() {
  local max_rank threshold_rank
  max_rank="$(sev_rank "${1:-}")" || return 2
  threshold_rank="$(sev_rank "${2:-}")" || return 2
  [ "$max_rank" -ge "$threshold_rank" ]
}
