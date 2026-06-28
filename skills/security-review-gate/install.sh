#!/usr/bin/env bash
# Install the in-session security-review gate into a target git repo (opt-in).
#
#   install.sh [--local] [target-repo]
#
# Copies the gate scripts into <repo>/.security-review-gate/ and merges the
# PreToolUse hook into the repo's Claude settings. Idempotent.
#
#   --local   write to .claude/settings.local.json (personal, usually
#             gitignored) instead of .claude/settings.json (shared).
set -euo pipefail

GATE_DIRNAME=".security-review-gate"
MARKER="security-review-gate/pretooluse.sh"

usage() { echo "usage: install.sh [--local] [target-repo]" >&2; }

LOCAL=0
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --local) LOCAL=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "error: unknown option: $1" >&2; usage; exit 2 ;;
    *) TARGET="$1" ;;
  esac
  shift
done

SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="${TARGET:-$PWD}"

command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }
ROOT="$(git -C "$TARGET" rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "error: '$TARGET' is not inside a git repository" >&2; exit 1; }

# Copy scripts (clean, so reinstall never nests directories).
DEST="$ROOT/$GATE_DIRNAME"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SRC/lib" "$DEST/lib"
cp "$SRC/hooks/pretooluse.sh" "$DEST/pretooluse.sh"
cp "$SRC/approve.sh" "$DEST/approve.sh"
chmod +x "$DEST/pretooluse.sh" "$DEST/approve.sh"
[ -f "$SRC/VERSION" ] && cp "$SRC/VERSION" "$DEST/VERSION"

# Merge the PreToolUse hook into Claude settings.
if [ "$LOCAL" -eq 1 ]; then
  SETTINGS="$ROOT/.claude/settings.local.json"
else
  SETTINGS="$ROOT/.claude/settings.json"
fi
mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
jq empty "$SETTINGS" 2>/dev/null \
  || { echo "error: $SETTINGS is not valid JSON; fix it and re-run" >&2; exit 1; }

CMD='bash "$CLAUDE_PROJECT_DIR/.security-review-gate/pretooluse.sh"'
entry="$(jq -n --arg cmd "$CMD" '{
  matcher: "Bash",
  hooks: [
    {type:"command", command:$cmd, "if":"Bash(git push:*)"},
    {type:"command", command:$cmd, "if":"Bash(git merge:*)"}
  ]
}')"

tmp="$(mktemp)"
jq --argjson entry "$entry" --arg marker "$MARKER" '
  .hooks = (.hooks // {})
  | .hooks.PreToolUse = (
      ((.hooks.PreToolUse // [])
        | map(select(any(.hooks[]?; (.command // "") | test($marker)) | not)))
      + [$entry]
    )
' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"

echo "Installed security-review gate into $ROOT"
echo "  - PreToolUse hook in ${SETTINGS#"$ROOT"/} (gates git push and git merge into main)"
echo
echo "Commit $GATE_DIRNAME/ and the settings change to share the gate, or add them"
echo "to .gitignore to keep it personal."
echo
echo "NOTE: this gate fires only inside Claude Code sessions. Pushes you run by hand"
echo "in a terminal are not gated."
