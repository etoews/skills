# Claude Skills

A personal collection of [Claude](https://claude.com/claude-code) skills.

## Skills

| Skill | Summary |
|-------|---------|
| [security-review-gate](skills/security-review-gate/) | In-session gate that requires a `/security-review`, with approval recorded for the commit, before Claude runs `git push` or `git merge` into `main`. Opt-in per repo. |

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
```

## Using these skills

Symlink or copy a skill directory into one of the locations Claude Code
discovers skills:

- `~/.claude/skills/`: available in every project
- `<project>/.claude/skills/`: scoped to a single project

## Adding a skill

Each skill lives in its own directory under `skills/`. Skills are authored
with the skill-creation workflow, which handles structure, frontmatter, and
progressive disclosure.
