#!/usr/bin/env bash
# Test runner: executes each tests/test_*.sh as its own process and reports a
# summary. Exit status is nonzero if any test file failed.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
pass=0
fail=0
failed_files=""

for t in "$here"/test_*.sh; do
  [ -e "$t" ] || continue
  name="$(basename "$t")"
  printf '* %s\n' "$name"
  if bash "$t"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    failed_files="$failed_files $name"
  fi
done

echo "------------------------------------------------------------"
if [ "$fail" -gt 0 ]; then
  printf 'FAIL: %d file(s) failed:%s\n' "$fail" "$failed_files" >&2
  exit 1
fi
printf 'OK: %d test file(s) passed\n' "$pass"
