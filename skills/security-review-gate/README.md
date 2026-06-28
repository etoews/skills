# security-review-gate

A hard security-review gate for git. It runs the `/security-review` command and
**blocks high/critical findings before code reaches `main`** — both when you run
git by hand and when Claude runs it in a session. Opt-in per repository.

See [`SKILL.md`](SKILL.md) for install/usage. This file covers how it works and
the one item still to validate end-to-end.

## Architecture

```
                 ┌─────────────────────── lib/ (shared) ───────────────────────┐
 git push  ─────▶│ gate.sh  ──▶ severity.sh  cache.sh  review.sh  log.sh        │
 (pre-push hook) │   bypass? → cache hit? → run /security-review → decide →     │
 git merge ─────▶│   cache verdict → allow (0) / block (1) / fail-closed (3)    │
 (PreToolUse)    └──────────────────────────────────────────────────────────────┘
```

- **`lib/severity.sh`** — pure ranking + the block/allow decision against the
  threshold.
- **`lib/cache.sh`** — SHA-keyed verdict cache under `.git/` (never committed).
  Coordinates the two hooks so the same commit is reviewed once.
- **`lib/review.sh`** — builds the headless request and extracts a
  schema-validated verdict from `claude -p --output-format json`. The verdict
  lands in `.structured_output` (with a `.result` string fallback).
- **`lib/gate.sh`** — the orchestrator both hooks call: bypass → cache → review
  → severity decision → cache → human summary, with structured log events.
- **`hooks/pre-push`** — git hook: reads ref updates, reviews the pushed range,
  aborts on block. The universal backstop.
- **`hooks/pretooluse.sh`** — Claude Code hook: detects in-session `git push` /
  `git merge` into main, emits `permissionDecision: deny` on block. The primary
  path. Never wedges a session: if it cannot load, it allows and relies on the
  pre-push backstop.
- **`install.sh` / `uninstall.sh`** — per-repo wiring (copy scripts, set
  `core.hooksPath`, merge the PreToolUse hook into Claude settings).

## Design decisions

- **Fail closed.** A missing `claude`, an error envelope, a budget cap, or an
  unparseable verdict all **block** (exit 3) with the bypass hint printed — never
  a silent gap.
- **ff-merge reality.** Git has no native pre-fast-forward-merge hook, so merges
  are gated in-session via the PreToolUse hook, and the pre-push hook enforces at
  the push boundary for everyone.
- **Threshold default `high`.** Lower findings are surfaced as warnings but do
  not block. Configurable.

## Testing

```bash
bash tests/run.sh
```

Dependency-free bash harness (no bats). A stub `claude`
(`tests/stubs/claude-stub.sh`) emits canned envelopes matching the real CLI
shape, so the suite is hermetic and spends no tokens. Coverage: severity
decisions, cache round-trip/coordination, verdict parsing and rejection,
gate allow/block/threshold/fail-closed plus logged events, both hooks, and
install/uninstall (idempotency, foreign-settings preservation, the installed
hook actually blocking, hooksPath guard).

## Open validation item

The headless **mechanism** is validated (envelope shape, `--json-schema`
→ `.structured_output`, read-only tools, cost cap). What still needs a live
end-to-end check is the **content contract**: confirm that
`claude -p "/security-review …"` over a real diff returns a verdict whose
`max_severity` and `findings` populate as expected, and tune the prompt
(`SECURITY_REVIEW_PROMPT`) and allowed-tools if the command needs more than the
read-only git set. The runner is structured so this is a config change, not a
rewrite. Until then, fail-closed means a misbehaving review blocks rather than
waves code through.
