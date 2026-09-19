# Claude Skills

A personal collection of [Claude](https://claude.com/claude-code) skills.

## Skills

| Skill | Summary |
|-------|---------|
| [ai-eval](skills/ai-eval/) | Run a repeatable LLM evaluation in a local Docker Compose [Arize Phoenix](https://github.com/Arize-ai/phoenix) against your own prompts and ground-truth answers. Each run is a Phoenix experiment tagged with its model/effort/params, scored for correctness, relevance, and faithfulness, so a candidate can be compared against a baseline. Provider-agnostic via LiteLLM; runs offline (no API key) for a pipeline smoke test. |
| [brainstorm-with-docs](skills/brainstorm-with-docs/) | Thin conductor that runs `superpowers:brainstorming`, then `grill-with-docs` against the committed spec (glossary, ADRs), then `superpowers:writing-plans`. Copies nothing from the upstream skills so their updates keep flowing. |
| [security-review-gate](skills/security-review-gate/) | In-session gate that requires a `/security-review`, with approval recorded for the commit, before Claude runs `git push` or `git merge` into `main`. Opt-in per repo. |
| [summary](skills/summary/) | Make a single-page HTML summary of the session since the last summary. Visual first: tables, charts, and diagrams instead of long text. Runs on Opus at low effort. |

## What is a skill?

A skill is a directory containing a `SKILL.md` file with YAML frontmatter
(`name`, `description`) plus Markdown instructions Claude follows when the
skill is relevant. A skill can bundle supporting files (scripts, references,
templates) alongside `SKILL.md`.

## Layout

```
skills/
  <skill-name>/
    SKILL.md        # frontmatter + instructions
    references/     # optional supporting docs
    scripts/        # optional helper scripts
.claude/skills/
  sync/             # repo-management skill, not distributed
```

`skills/` holds the skills this repo publishes. `.claude/skills/` holds skills
that only manage this repo: `/sync` keeps the repo, its remote, and the
installed symlinks in step, and its `scripts/status.sh` is a read-only audit of
that state.

## Using these skills

Symlink or copy a skill directory into one of the locations Claude Code
discovers skills:

- `~/.claude/skills/`: available in every project
- `<project>/.claude/skills/`: scoped to a single project

These skills are installed with symlinks pointing at this working tree, so an
edit here is live in every project at once, and whichever branch is checked out
here is the one every project runs. Run `/sync` to check and repair that state.

## Adding a skill

Each skill lives in its own directory under `skills/`. Skills are authored
with the skill-creation workflow, which handles structure, frontmatter, and
progressive disclosure.
