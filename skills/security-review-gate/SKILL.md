---
name: security-review-gate
description: Use when the user wants to install, configure, or manage a hard security-review gate that blocks high/critical findings before a git merge to main or a branch push. Wires up a git pre-push hook plus a Claude Code PreToolUse hook that run /security-review headlessly and fail closed.
---

# Security Review Gate

A hard gate that runs the `/security-review` command and **blocks** when it finds
issues at or above a severity threshold (default `high`), before code reaches
`main`. Opt-in per repository.

## What it installs

Two coordinated hooks that share one runner:

1. **git `pre-push` hook** — the universal backstop. Fires on every push
   regardless of who runs git (you, Claude, an IDE). Reviews the commits being
   pushed; aborts the push on high/critical findings.
2. **Claude Code `PreToolUse` hook** — the primary, in-session gate. Fires
   before Claude runs `git push` or `git merge` into `main`/`master`; denies the
   tool call (Claude sees the findings and stops) on high/critical.

A **SHA-keyed verdict cache** under `.git/` coordinates the two so the same
commits are never reviewed twice, and the gate **fails closed** (blocks) if the
review cannot complete.

## Install / uninstall

Run from inside the target repo, or pass its path:

```bash
# install (shared settings)
bash <path-to-skill>/install.sh [target-repo]
# install but keep the Claude hook personal (.claude/settings.local.json)
bash <path-to-skill>/install.sh --local [target-repo]
# remove
bash <path-to-skill>/uninstall.sh [target-repo]
```

Install copies the scripts to `<repo>/.security-review-gate/`, sets
`core.hooksPath`, and merges the PreToolUse hook into Claude settings. It is
idempotent and refuses to clobber an existing `core.hooksPath`.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECURITY_REVIEW_THRESHOLD` | `high` | Block at/above this severity (`low`..`critical`). |
| `SECURITY_REVIEW_MODEL` | `sonnet` | Model used for the headless review. |
| `SECURITY_REVIEW_MAX_USD` | `1.00` | Per-review cost cap. |
| `SECURITY_REVIEW_PROMPT` | built-in | Override the review prompt (`{RANGE}` is substituted). |
| `SECURITY_REVIEW_ALLOWED_TOOLS` | read-only git + Read/Grep/Glob | Tools the review may use. |
| `SKIP_SECURITY_REVIEW` | unset | Set truthy to bypass both hooks. |
| `GATE_LOG_LEVEL` / `GATE_LOG_FILE` | `info` / unset | Observability. |

## Bypass (use sparingly)

- `git push --no-verify` skips the pre-push hook.
- `SKIP_SECURITY_REVIEW=1` bypasses both hooks.

## Requirements

- `jq` and the `claude` CLI on `PATH`.
- The gate runs `/security-review` via `claude -p`, so each gated push/merge
  spends tokens; the cache avoids re-paying for the same commits.

## Coexistence with the security-guidance plugin

That plugin does a **soft, async** review on push/commit. This gate is the
**hard** block. If both are installed, disable the plugin's push/commit review
to avoid double LLM reviews on in-session pushes.

## Verifying a change to the gate itself

```bash
bash <path-to-skill>/tests/run.sh
```

The suite uses a stub `claude`, so it is fast, hermetic, and spends no tokens.
See `README.md` for architecture and the one open validation item (the exact
headless `/security-review` verdict contract).
