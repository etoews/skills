#!/usr/bin/env bash
# Install the security-review gate into a target git repo (opt-in, per repo).
#
#   install.sh [--local] [target-repo]
#
# Copies the gate scripts into <repo>/.security-review-gate/, points
# core.hooksPath at the bundled git pre-push hook, and merges the PreToolUse
# hook into the repo's Claude settings. Idempotent: re-running refreshes the
# scripts and leaves a single hook entry.
#
#   --local   write to .claude/settings.local.json (personal, usually
#             gitignored) instead of .claude/settings.json (shared).
set -euo pipefail

GATE_DIRNAME=".security-review-gate"
HOOKSPATH_REL="$GATE_DIRNAME/githooks"
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

# Refuse to clobber a foreign core.hooksPath.
existing_hp="$(git -C "$ROOT" config --local --get core.hooksPath || true)"
if [ -n "$existing_hp" ] && [ "$existing_hp" != "$HOOKSPATH_REL" ]; then
  echo "error: core.hooksPath is already set to '$existing_hp'." >&2
  echo "       Refusing to overwrite. Relocate those hooks under $HOOKSPATH_REL" >&2
  echo "       or unset core.hooksPath, then re-run." >&2
  exit 1
fi

# Copy scripts (clean, so reinstall never nests directories).
DEST="$ROOT/$GATE_DIRNAME"
rm -rf "$DEST"
mkdir -p "$DEST/githooks"
cp -R "$SRC/lib" "$DEST/lib"
cp "$SRC/hooks/pre-push" "$DEST/githooks/pre-push"
cp "$SRC/hooks/pretooluse.sh" "$DEST/pretooluse.sh"
chmod +x "$DEST/githooks/pre-push" "$DEST/pretooluse.sh"
[ -f "$SRC/VERSION" ] && cp "$SRC/VERSION" "$DEST/VERSION"

# Wire the git pre-push hook.
git -C "$ROOT" config --local core.hooksPath "$HOOKSPATH_REL"

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
echo "  - git pre-push hook via core.hooksPath=$HOOKSPATH_REL"
echo "  - PreToolUse hook in ${SETTINGS#"$ROOT"/}"
echo
echo "Commit $GATE_DIRNAME/ and the settings change to share the gate with the repo,"
echo "or add them to .gitignore to keep it personal."
echo
echo "If the security-guidance plugin is installed, disable its push/commit review"
echo "so in-session pushes are not reviewed twice; this gate is the hard gate."
