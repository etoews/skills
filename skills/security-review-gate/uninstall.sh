#!/usr/bin/env bash
# Remove the security-review gate from a target git repo.
#
#   uninstall.sh [target-repo]
#
# Unsets core.hooksPath (only if it points at our hook), strips our PreToolUse
# entry from both settings files, and deletes .security-review-gate/.
set -euo pipefail

GATE_DIRNAME=".security-review-gate"
HOOKSPATH_REL="$GATE_DIRNAME/githooks"
MARKER="security-review-gate/pretooluse.sh"

TARGET="${1:-$PWD}"
command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }
ROOT="$(git -C "$TARGET" rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "error: '$TARGET' is not inside a git repository" >&2; exit 1; }

# Unset hooksPath only if it is ours.
hp="$(git -C "$ROOT" config --local --get core.hooksPath || true)"
if [ "$hp" = "$HOOKSPATH_REL" ]; then
  git -C "$ROOT" config --local --unset core.hooksPath || true
fi

# Strip our PreToolUse entry from shared and local settings.
for SETTINGS in "$ROOT/.claude/settings.json" "$ROOT/.claude/settings.local.json"; do
  [ -f "$SETTINGS" ] || continue
  jq empty "$SETTINGS" 2>/dev/null || continue
  tmp="$(mktemp)"
  jq --arg marker "$MARKER" '
    if (.hooks.PreToolUse) then
      .hooks.PreToolUse = (.hooks.PreToolUse
        | map(select(any(.hooks[]?; (.command // "") | test($marker)) | not)))
      | (if (.hooks.PreToolUse == []) then del(.hooks.PreToolUse) else . end)
    else . end
  ' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
done

rm -rf "$ROOT/$GATE_DIRNAME"
echo "Removed security-review gate from $ROOT"
