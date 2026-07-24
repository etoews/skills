---
name: sync
description: Use whenever this skills repo and the machine that consumes it need to be brought back into line. Triggers include the user saying "sync", asking to push or pull this repo, adding or renaming or deleting a skill here, reporting that a skill is missing or stale in another project, saying an edit made here did not take effect, or having just changed a skill that should reach every project.
---

# Sync

This repo lives at `$HOME/dev/etoews/skills` and pushes to
`git@github.com:etoews/skills.git`. Each directory under `skills/` is a skill
that reaches every project through a symlink in `~/.claude/skills`. "Sync"
means: audit, pull, reconcile links, ff-merge the working branch, push, verify.
Always do all six, in that order, even if the user only asked for one of them.
Half a sync is how the repo and the live skills quietly diverge.

## Step 0: Audit

Run the read-only audit first and again at the end:

```sh
.claude/skills/sync/scripts/status.sh
```

It reports git state (ahead/behind, dirty files), link health in both
directions, name collisions with other skill sources, `SKILL.md` frontmatter
validity, and README coverage. It never mutates anything. When exercising this
skill against a sandbox copy, set `SKILLS_DIR` and `SKILLS_HOME` to point at
the sandbox.

## How skills reach the live system

| Repo path | Live path | Mechanism |
|---|---|---|
| `skills/<name>/` | `~/.claude/skills/<name>` | symlink, relative: `../../dev/etoews/skills/skills/<name>` |
| `.claude/skills/sync/` | this repo only | project-scoped, never linked |

The links point at the working tree, not a copy, which has a consequence worth
holding onto: **whatever branch is checked out here is what every project
runs.** A half-finished skill on a `feat/` branch is live everywhere while that
branch is checked out. Land work on `main` promptly and do not leave the repo
parked on a branch.

`.claude/skills/sync` is deliberately not a distributable skill. It manages
this repo, so it stays project-scoped and out of `skills/`.

## What each finding means and how to reconcile it

| Finding | Meaning | Fix |
|---|---|---|
| `MISSING` | A skill exists here with no link, usually one added on the other machine and just pulled | `ln -s ../../dev/etoews/skills/skills/<name> ~/.claude/skills/<name>` |
| `WRONG-TARGET` | Link resolves somewhere other than its own skill | Remove the link and recreate it |
| `NOT-A-SYMLINK` | A real directory sits at the live path, so edits here never reach it | If it diverges, move it to `<name>.pre-symlink.bak` first, then link. Never delete it outright |
| `STALE` (dangling) | Link points into this repo at something gone, usually a rename or deletion upstream | Confirm the skill really went away, then remove the link |
| `STALE` (no such skill) | Left over from a rename | Remove the link, and check the new name has one |
| `COLLISIONS WARN` | The name also exists in `~/.agents/skills`, and `~/.claude/skills` is one flat namespace | Rename this repo's skill. Never delete the other source |
| `VALIDITY FAIL` | Frontmatter is missing, malformed, or its `name` does not match the directory | Fix it here and commit |
| `README WARN` | The skill is not in the root `README.md` table | Add a row: the table is the repo's index |

Create links relative, as the table shows, matching the existing entries in
`~/.claude/skills`.

## Never commit it, never destroy it

Some state is deliberately local and must not reach the repo or be cleaned up:

- `skills/ai-eval/.env`: real API keys, gitignored. Never commit it, never
  delete it.
- `skills/ai-eval/.venv/`, `phoenix_data/`, `__pycache__/`, `.scratch/`:
  regenerable local state, gitignored, not drift to fix.
- Everything in `~/.claude/skills` that does not resolve into this repo: links
  into `~/.agents/skills`, plugin and marketplace skills. They are other
  people's, and out of scope. Never remove or repoint a link the audit did not
  attribute to this repo.

When a diff or a link is one you cannot confidently classify, show it to the
user and ask. Wrong guesses here either leak a secret or delete someone's work.

## The procedure

1. **Audit** and classify what it found into: repo changes to share, local
   state to leave alone, and link drift to reconcile.
2. **Pull with rebase.** `git pull --rebase` on `main`. Never create a merge
   commit; if both machines committed, rebase keeps history linear.
3. **Reconcile links** per the table above, after the pull, so newly pulled
   skills get their links in the same pass.
4. **Commit, ff-merge, and push.** Development happens on a `feat/<slug>`
   branch, never on `main` (the global git rules require this), so
   the changes to share usually sit on that branch. Commit them there with a
   message in this repo's style from `git log`: a capitalised imperative
   sentence, for example `Add sync skill`. Then ship it: invoking `/sync` is
   the go signal, so it satisfies the "review before ff-merge" gate in the
   global rules. Rebase the `feat/*` branch onto the freshly pulled `main` so
   it fast-forwards, check out `main`, `git merge --ff-only`, delete the merged
   branch, and push. If `.security-review-gate/` exists in the repo, the push
   needs an approval receipt first: run `/security-review`. If `/sync` was
   invoked from `main`, there is nothing to merge. Other `feat/*` branches are
   left untouched.
5. **Verify.** Re-run the audit, confirm it is clean, then report.

## Adding, renaming, or deleting a skill

Each of these is three changes, not one, and the audit fails until all three
are done: the directory under `skills/`, the link in `~/.claude/skills`, and
the row in the root `README.md`. A rename is a delete plus an add: remove the
old link rather than leaving it dangling.

## After syncing, tell the user what still needs a human

Claude Code has picked up newly created links inside a running session, so a
restart is usually unnecessary. If a session does not see a skill that was
added, renamed, or removed, restart it. Nothing else needs a restart, because
the links point at the working tree.

## Report format

End with exactly this shape, dropping lines that do not apply:

```
## Sync report
- Pulled: <n> commits: <one-line summary> | already up to date
- Merged: <branch> -> main (ff) | nothing to merge
- Pushed: <n> commits: <one-line summary> | nothing to push
- Links fixed: <list> | all healthy
- Stale links removed: <list>
- Left alone (not this repo's): <list>
- Action needed: restart session | none
```

## Scope

This skill touches only this repo, its remote, and the links under
`~/.claude/skills` that resolve into this repo. Nothing else on the machine is
in scope, and nothing here is ever force-pushed; if a push is rejected, fetch
and rebase again.
