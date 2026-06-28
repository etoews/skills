#!/usr/bin/env bash
# SHA-keyed review-approval receipts.
#
# A receipt records that a security review was run and approved for a specific
# commit SHA, so the PreToolUse gate lets that commit be pushed/merged. Receipts
# live under .git/ (never committed; local to the clone) so they cannot be
# forged via a tracked file and are wiped with the repo.

# _receipt_dir : honour $GATE_RECEIPT_DIR (tests/advanced), else under .git/.
_receipt_dir() {
  if [ -n "${GATE_RECEIPT_DIR:-}" ]; then
    printf '%s' "$GATE_RECEIPT_DIR"
  else
    local gd
    gd="$(git rev-parse --git-dir 2>/dev/null)" || return 1
    printf '%s/security-review-gate-receipts' "$gd"
  fi
}

# receipt_exists <sha> : exit 0 if an approval receipt exists for the SHA.
receipt_exists() {
  local f
  f="$(_receipt_dir)/$1" || return 1
  [ -s "$f" ]
}

# receipt_record <sha> <note> : store an approval receipt. exit 0 on success.
receipt_record() {
  local dir
  dir="$(_receipt_dir)" || return 1
  mkdir -p "$dir" || return 1
  printf '%s\n' "$2" > "$dir/$1"
}

# receipt_get <sha> : print the receipt note; exit 1 if none.
receipt_get() {
  local f
  f="$(_receipt_dir)/$1" || return 1
  [ -s "$f" ] || return 1
  cat "$f"
}
