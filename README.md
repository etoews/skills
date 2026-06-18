# skills

My personal [Claude Code](https://docs.claude.com/en/docs/claude-code) [agent skills](https://docs.claude.com/en/docs/claude-code/skills).

Each top-level directory is a self-contained skill: a `SKILL.md` plus any
`references/`, `scripts/`, `assets/` and `evals/` it needs.

## Skills

- **[nz-grocery-compare](nz-grocery-compare/)**: comparison-shop a grocery basket
  across New Zealand's main supermarket sites (Woolworths, New World, PAK'nSAVE and
  Four Square), reconcile the real cart prices, and build an interactive HTML
  price-comparison report plus an over-time trend report.

## Installing

Claude Code loads skills from `~/.claude/skills/`. Symlink each skill from this repo
into that directory so edits here stay live:

```sh
ln -s "$PWD/nz-grocery-compare" ~/.claude/skills/nz-grocery-compare
```
