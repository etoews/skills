---
name: brainstorm-with-docs
description: Design pipeline that runs superpowers:brainstorming to turn an idea into a spec, then grill-with-docs to challenge the spec against the project's domain model (CONTEXT.md glossary and ADRs), then superpowers:writing-plans. Use when starting feature design in a repo that documents its ubiquitous language and decisions, or when the user says "brainstorm with docs".
---

# Brainstorm With Docs

A thin conductor. It invokes three upstream skills in order and adds only the glue between them. Never copy content from those skills into this one; invoke them by name via the Skill tool so upstream updates keep flowing.

**Announce at start:** "I'm using the brainstorm-with-docs skill to run brainstorming, then a docs grill, then planning."

## The pipeline

1. Invoke `superpowers:brainstorming`
2. At the seam (below), invoke `grill-with-docs`
3. Invoke `superpowers:writing-plans`

## 1. Brainstorming, with two adjustments

Invoke `superpowers:brainstorming` and run it in full, through its spec write, self-review, and user review of the spec, with these per-invocation instructions:

- **Glossary nudge:** during its project-context exploration, if a `CONTEXT.md` (or `CONTEXT-MAP.md`) exists, read it and use its canonical terms throughout the clarifying questions and the spec. If none exists, skip this; grill-with-docs creates one lazily later.
- **Terminal override:** brainstorming instructs that the only skill invoked after it is writing-plans. That does not apply here. Do NOT invoke writing-plans when brainstorming finishes; this skill owns that transition.

## 2. The seam: grill the committed spec

When the spec is written, committed, and approved by the user, but before any plan exists, invoke `grill-with-docs` against the spec.

Scope it as a **delta pass**, not a second design interview; the user has just been interviewed by brainstorming. Focus on grill-with-docs's unique value: challenge the spec's terminology against the glossary, stress-test it with concrete scenarios, cross-reference its claims with the code, and capture resolved terms in `CONTEXT.md` and hard-to-reverse decisions as ADRs.

**Loop back on design holes:** if the grill exposes a design hole (not just a fuzzy term), return to brainstorming to revise the spec, then re-grill what changed.

## 3. Hand off to planning

grill-with-docs has no terminal handoff; it simply stops when shared understanding is reached. When it does, invoke `superpowers:writing-plans`.

**Stop there.** This skill ends exactly where brainstorming would have ended, by invoking writing-plans. Do not wrap executing-plans, TDD, code review, or anything else downstream.

## Update safety

- Reference the seam only by the semantic event above, never by a step number in brainstorming's checklist; upstream renumbering would silently misfire.
- Never restate what the upstream skills do or copy their formats (for example grill-with-docs's `CONTEXT-FORMAT.md` and `ADR-FORMAT.md`). Invoke the skills and let them speak for themselves.
