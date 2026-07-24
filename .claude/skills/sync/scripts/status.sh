#!/bin/bash
# Read-only audit of skills sync state. Prints a report; never mutates the
# repo, the remote, or anything under ~/.claude/skills (the only network
# call is a git fetch to learn ahead/behind counts).
#
# Overrides (used when exercising the skill against a sandbox copy):
#   SKILLS_DIR   defaults to $HOME/dev/etoews/skills
#   SKILLS_HOME  defaults to $HOME

set -u

DIR="${SKILLS_DIR:-$HOME/dev/etoews/skills}"
H="${SKILLS_HOME:-$HOME}"
LIVE="$H/.claude/skills"

if [ ! -d "$DIR/.git" ]; then
  echo "FAIL: no git repo at $DIR"
  exit 1
fi

DIR_P=$(cd -P "$DIR" && pwd)

# Physical path a symlink points at, resolved even when the final component
# no longer exists (a dangling link still has to be reported by target).
resolve_link() {
  local link="$1" raw parent base
  raw=$(readlink "$link")
  case "$raw" in
    /*) ;;
    *) raw="$(cd -P "$(dirname "$link")" && pwd)/$raw" ;;
  esac
  parent=$(dirname "$raw")
  base=$(basename "$raw")
  if [ -d "$parent" ]; then
    echo "$(cd -P "$parent" && pwd)/$base"
  else
    echo "$raw"
  fi
}

# Abbreviate paths under the home directory so the report stays readable.
short() {
  case "$1" in
    "$H"/*) echo "~/${1#"$H"/}" ;;
    *) echo "$1" ;;
  esac
}

# Every directory under skills/ that carries a SKILL.md, one per line.
skill_names() {
  for d in "$DIR"/skills/*/; do
    [ -d "$d" ] || continue
    [ -f "$d/SKILL.md" ] || continue
    basename "$d"
  done
}

echo "== GIT =="
branch=$(git -C "$DIR" rev-parse --abbrev-ref HEAD)
echo "branch: $branch"
[ "$branch" != "main" ] && echo "WARN: not on main"

if git -C "$DIR" fetch --quiet origin 2>/dev/null; then
  counts=$(git -C "$DIR" rev-list --left-right --count origin/main...HEAD 2>/dev/null)
  behind=$(echo "$counts" | awk '{print $1}')
  ahead=$(echo "$counts" | awk '{print $2}')
  echo "behind origin/main: ${behind:-?}   ahead of origin/main: ${ahead:-?}"
else
  echo "WARN: fetch failed (offline?); ahead/behind unknown"
fi

dirty=$(git -C "$DIR" status --porcelain)
if [ -n "$dirty" ]; then
  echo "uncommitted changes:"
  echo "$dirty" | sed 's/^/  /'
else
  echo "working tree clean"
fi

stashes=$(git -C "$DIR" stash list | wc -l | tr -d ' ')
[ "$stashes" != "0" ] && echo "WARN: $stashes stash(es) present"

echo ""
echo "== LINKS =="
# Forward: every skill in the repo should be reachable as a user skill.
if [ ! -d "$LIVE" ]; then
  echo "WARN: $LIVE does not exist; no skill is installed"
fi
skill_names | while IFS= read -r name; do
  tgt="$LIVE/$name"
  src="$DIR_P/skills/$name"
  if [ -L "$tgt" ]; then
    dest=$(resolve_link "$tgt")
    if [ ! -e "$tgt" ]; then
      echo "BROKEN: $(short "$tgt") -> $(short "$dest") (dangling)"
    elif [ "$dest" = "$src" ]; then
      echo "OK: $(short "$tgt") -> skills/$name"
    else
      echo "WRONG-TARGET: $(short "$tgt") -> $(short "$dest") (expected skills/$name)"
    fi
  elif [ -d "$tgt" ]; then
    if diff -rq "$tgt" "$src" >/dev/null 2>&1; then
      echo "NOT-A-SYMLINK: $(short "$tgt") is a real directory (matches repo now, but edits will not flow)"
    else
      echo "NOT-A-SYMLINK: $(short "$tgt") is a real directory and DIVERGES from skills/$name"
    fi
  elif [ -e "$tgt" ]; then
    echo "NOT-A-SYMLINK: $(short "$tgt") exists and is not a directory"
  else
    echo "MISSING: $(short "$tgt") (should link to skills/$name)"
  fi
done

# Reverse: links under ~/.claude/skills that point into this repo under a
# name that is no longer a skill here (renamed or deleted). Links named
# after a current skill are already covered by the forward pass.
for l in "$LIVE"/*; do
  [ -L "$l" ] || continue
  dest=$(resolve_link "$l")
  case "$dest" in
    "$DIR_P"/*) ;;
    *) continue ;;
  esac
  name=$(basename "$l")
  [ -f "$DIR_P/skills/$name/SKILL.md" ] && continue
  if [ ! -e "$l" ]; then
    echo "STALE: $(short "$l") -> $(short "$dest") (dangling; skill renamed or deleted?)"
  else
    echo "STALE: $(short "$l") -> $(short "$dest") (no skills/$name in the repo; left over from a rename?)"
  fi
done

echo ""
echo "== COLLISIONS =="
# ~/.claude/skills is one flat namespace. A name this repo shares with
# another skill source can only be installed from one of them.
found_collision=0
for name in $(skill_names); do
  other="$H/.agents/skills/$name"
  if [ -e "$other" ]; then
    echo "WARN: $name also exists in $(short "$other"); only one can be installed"
    found_collision=1
  fi
done
[ "$found_collision" = "0" ] && echo "no name collisions with $(short "$H/.agents/skills")"

echo ""
echo "== VALIDITY =="
for d in "$DIR"/skills/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  f="$d/SKILL.md"
  if [ ! -f "$f" ]; then
    echo "WARN: skills/$name has no SKILL.md (not a skill; never linked)"
    continue
  fi
  if [ "$(head -1 "$f")" != "---" ]; then
    echo "FAIL: skills/$name/SKILL.md does not open with YAML frontmatter"
    continue
  fi
  fm=$(awk 'NR==1 && $0=="---" {inb=1; next} inb && $0=="---" {exit} inb {print}' "$f")
  fmname=$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p' | head -1)
  desc=$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p' | head -1)
  problems=""
  [ "$fmname" = "$name" ] || problems="$problems name '$fmname' does not match directory;"
  [ -n "$desc" ] || problems="$problems no description;"
  chars=$(printf '%s\n' "$fm" | wc -c | tr -d ' ')
  [ "$chars" -le 1024 ] || problems="$problems frontmatter is $chars chars (limit 1024);"
  if [ -n "$problems" ]; then
    echo "FAIL: skills/$name:$problems"
  else
    echo "OK: skills/$name (frontmatter, $chars chars)"
  fi
done

echo ""
echo "== README =="
for name in $(skill_names); do
  if grep -q "skills/$name/" "$DIR/README.md" 2>/dev/null; then
    echo "OK: $name listed in README.md"
  else
    echo "WARN: $name is not in the README.md skills table"
  fi
done

echo ""
echo "== NOTES =="
for f in "$DIR"/skills/*/.env; do
  [ -f "$f" ] && echo "machine-local file present: ${f#"$DIR"/} (gitignored; never commit, never delete)"
done
exit 0
