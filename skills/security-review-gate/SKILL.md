---
name: security-review-gate
description: Use when the user wants to install, configure, or manage an in-session gate that requires a /security-review (with approval recorded for the commit) before Claude runs a git push or a git merge into main. Opt-in per repo, receipt-based, bypassable with SKIP_SECURITY_REVIEW.
---

# Security Review Gate

An in-session gate that requires a security review before Claude pushes or merges
to `main`. When Claude is about to run `git push` or `git merge` into
`main`/`master`, the gate checks for an **approval receipt** for the commit being
introduced. No receipt → the action is **denied** with instructions to run
`/security-review` and record approval. Opt-in per repository.

> **Scope:** this gate fires **only inside Claude Code sessions** (it is a
> `PreToolUse` hook). Pushes you run by hand in a terminal, an IDE, or CI are not
> gated. Enforcement is cooperative: a hook cannot run or verify the interactive
> `/security-review` itself, so it relies on the approval step being run honestly.

## How it works

1. Claude is about to run `git push` / `git merge` into main.
2. The `PreToolUse` hook computes the commit SHA being introduced and looks for a
   receipt.
   - **Receipt present** → allow.
   - **No receipt** → **deny**, telling Claude to run `/security-review` over the
     relevant range and, if there are no findings at or above the threshold,
     record approval:
     ```
     bash .security-review-gate/approve.sh <sha> [max_severity]
     ```
3. `approve.sh` records a receipt for that SHA (refusing if `max_severity` is at
   or above the threshold). Claude retries the push/merge and it proceeds.

Receipts are keyed by commit SHA and stored under `.git/` (never committed), so
re-pushing the same commit does not re-prompt.

## Install / uninstall

```bash
bash <path-to-skill>/install.sh [target-repo]      # shared settings
bash <path-to-skill>/install.sh --local [target-repo]   # personal settings.local.json
bash <path-to-skill>/uninstall.sh [target-repo]
```

Install copies the scripts to `<repo>/.security-review-gate/` and merges the
PreToolUse hook into Claude settings. Idempotent. No git hooks are touched.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECURITY_REVIEW_THRESHOLD` | `high` | Severity at/above which approval is required; `approve.sh` refuses a higher `max_severity`. |
| `SKIP_SECURITY_REVIEW` | unset | Set truthy to bypass the gate. |
| `GATE_LOG_LEVEL` / `GATE_LOG_FILE` | `info` / unset | Observability. |

## Coexistence with the security-guidance plugin

That plugin does a soft, async LLM review on push/commit and is complementary:
it can run the review automatically while this gate enforces the
approval-before-merge/push step. They do not conflict (this gate runs no LLM
itself).

## Verifying a change to the gate itself

```bash
bash <path-to-skill>/tests/run.sh
```

Dependency-free bash suite; fast, hermetic, spends no tokens. See `README.md`
for architecture and the trust model.
