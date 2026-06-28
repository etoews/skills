# security-review-gate

An in-session gate that requires a security review before Claude pushes or merges
to `main`. It is a Claude Code `PreToolUse` hook that blocks `git push` / `git
merge` into main until an **approval receipt** exists for the commit being
introduced. Opt-in per repository.

See [`SKILL.md`](SKILL.md) for install/usage. This file covers how it works, the
trust model, and its limits.

## Flow

```
Claude: git push / git merge into main
   │
   ▼
PreToolUse hook ── receipt for this commit SHA?
   ├── yes ─────────────────────────────────▶ allow
   └── no  ─▶ deny: "run /security-review, then approve.sh <sha>"
                │
                ▼
        Claude runs /security-review (interactive)
                │  no findings ≥ threshold
                ▼
        approve.sh <sha> [max_severity]  ──▶ records receipt under .git/
                │
                ▼
        Claude retries push/merge ──────────▶ allow
```

## Components

- **`hooks/pretooluse.sh`** — detects in-session `git push` and `git merge` into
  `main`/`master`, computes the commit SHA, allows on a receipt (or
  `SKIP_SECURITY_REVIEW`), otherwise denies with actionable instructions. Never
  wedges the session: if it cannot load its library, it allows.
- **`approve.sh <sha> [max_severity]`** — records an approval receipt for a
  commit; refuses if `max_severity` is at or above the threshold, or if the
  severity/commit is invalid.
- **`lib/receipt.sh`** — SHA-keyed receipts under `.git/` (never committed).
- **`lib/severity.sh`** — severity ranking + the at/above-threshold decision.
- **`lib/gate.sh`** — umbrella that sources the leaf modules and provides
  `gate_truthy` / `gate_threshold`.
- **`lib/log.sh`** — structured log events for observability.
- **`install.sh` / `uninstall.sh`** — per-repo wiring of the PreToolUse hook in
  Claude settings (no git hooks).

## Trust model and limits

- **In-session only.** As a `PreToolUse` hook it fires only when Claude runs git.
  Manual terminal pushes, IDE pushes, and CI are not gated. (An earlier design
  added a git `pre-push` backstop for those; it was intentionally removed.)
- **Cooperative, not verified.** A shell hook cannot run the interactive
  `/security-review` or independently confirm one happened. The gate enforces
  that an approval *receipt* exists; the receipt is written by `approve.sh`,
  which Claude runs after reviewing. The threshold guard in `approve.sh` is a
  guardrail, not a cryptographic check.
- **Why not headless?** Driving `/security-review` through `claude -p` runs zero
  turns and returns nothing (the command is interactive-only; confirmed by a live
  spike), so the gate uses the real interactive command plus a receipt instead.

## Testing

```bash
bash tests/run.sh
```

Dependency-free bash harness (no bats), hermetic, no tokens. Coverage: severity
decisions, receipt round-trip/isolation, the PreToolUse hook
(deny/allow/bypass/merge-vs-push/non-gated), `approve.sh`
(record/refuse-on-severity/invalid input), and install/uninstall (idempotency,
foreign-settings preservation, the installed hook denying without a receipt and
allowing with one).
