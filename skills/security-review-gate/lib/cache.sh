#!/usr/bin/env bash
# SHA-keyed verdict cache.
#
# Stores the (expensive) review verdict JSON keyed by the commit SHA being
# introduced, so the same commits are not reviewed twice: the in-session
# PreToolUse hook records a verdict, and the git pre-push hook reuses it
# instead of paying for a second LLM review. Also saves cost on retried pushes.

# _cache_dir : resolve the cache directory.
#   Honours $GATE_CACHE_DIR (used by tests and advanced setups); otherwise the
#   cache lives under the repo's git dir, so it is never committed and is wiped
#   when the repo is removed.
_cache_dir() {
  if [ -n "${GATE_CACHE_DIR:-}" ]; then
    printf '%s' "$GATE_CACHE_DIR"
  else
    local gd
    gd="$(git rev-parse --git-dir 2>/dev/null)" || return 1
    printf '%s/security-review-gate-cache' "$gd"
  fi
}

# cache_get <sha> : print the stored verdict for a SHA on stdout.
#   exit 0 if a non-empty verdict exists, 1 otherwise.
cache_get() {
  local f
  f="$(_cache_dir)/$1" || return 1
  [ -s "$f" ] || return 1
  cat "$f"
}

# cache_put <sha> <verdict_json> : store a verdict for a SHA. exit 0 on success.
cache_put() {
  local dir
  dir="$(_cache_dir)" || return 1
  mkdir -p "$dir" || return 1
  printf '%s' "$2" > "$dir/$1"
}
