# ai-eval skill — design

**Date:** 2026-07-03
**Status:** Approved (design), implementation in progress

## Purpose

A skill that lets someone run a repeatable AI evaluation in a locally-hosted
[Arize Phoenix](https://github.com/Arize-ai/phoenix) (Docker Compose) against a
set of prompts with known-good ("ground truth") responses. You define the
prompts + ground truth once; each run executes one model / effort / parameter
configuration against them and records the result as a Phoenix **experiment**,
tagged with that configuration. LLM-as-judge evaluators score each answer for
**correctness**, **relevance**, and **faithfulness** against the ground truth.
Phoenix's experiment-comparison UI then shows how a candidate config (e.g. a new
model like Fable 5 on xhigh) stacks up against a baseline (e.g. Opus 4.8 on
xhigh) on the prompts that matter to you — surfacing regressions and what needs
to change about prompting.

## Load-bearing decisions

1. **Model invocation: LiteLLM.** Provider-agnostic, so the same prompts can be
   run against Claude, GPT, Gemini, etc. `effort` maps per-provider (Anthropic:
   extended-thinking `budget_tokens`; others: their nearest reasoning knob) via
   LiteLLM's `reasoning_effort`. A `--param k=v` passthrough covers other LLM
   parameters. Isolated in `model.py` so a provider is a small change.
2. **Dataset format: YAML, one file per case in a directory.** Each file holds
   `input`, `expected` (a single ground-truth string), and optional `metadata`.
   The loader globs the directory (stable sort by filename) and upserts a
   Phoenix dataset named after the directory, so re-runs version the same
   dataset.
3. **Metrics: Correctness + Relevance + Faithfulness.** All grounded against the
   ground-truth answer (no retrieval/RAG context here):
   - **Correctness** — does the answer match the ground truth's facts?
   - **Relevance** — does the answer actually address the question?
   - **Faithfulness** — does the answer avoid claims that contradict or go
     beyond the ground truth? (Replaces the deprecated Hallucination metric.)
   Each is an LLM-as-judge returning a score (1/0), a label, and an explanation.
   Extensible with more evaluators.
4. **Offline stub mode.** `--offline` swaps the task model and the judge for
   deterministic stubs (no API calls), so the full pipeline (Docker Phoenix →
   dataset → experiment → evaluators → results) runs and is provable with no API
   key. Real numbers require `ANTHROPIC_API_KEY` (or the relevant provider key)
   and dropping `--offline`. Offline mode also makes the tests hermetic.

## Architecture

Phoenix is the harness (stores datasets, orchestrates experiments, records
scores, provides the compare UI). It never calls a model itself. The skill
supplies: the prompts+ground-truth (dataset), the thing under test (task), and
the graders (evaluators).

```
skills/ai-eval/
  SKILL.md              # when-to-use + quickstart; detail pushed to references/
  README.md             # architecture, data flow, limits
  compose.yaml          # arizephoenix/phoenix:latest, ports 6006/4317, named volume
  pyproject.toml        # arize-phoenix(+client), phoenix-evals, litellm, pyyaml, pandas, dotenv
  scripts/
    run_eval.py         # CLI entrypoint: config -> load cases -> upsert dataset -> run_experiment -> summary
    config.py           # RunConfig, effort map, CLI parsing, offline resolution
    dataset.py          # load YAML case dir -> cases; upsert Phoenix dataset
    model.py            # task fn: format prompt, call LiteLLM (real) or deterministic stub (offline)
    evaluators.py       # 3 create_evaluator(kind="LLM") judges: phoenix.evals LLM (real) or heuristic (offline)
  datasets/example/     # 3 cases, one YAML file each (the done-criterion demo data)
  references/
    metrics.md          # each metric's meaning + the judge prompt/schema
    providers.md        # effort mapping per provider; adding a provider/metric
  tests/
    test_*.py           # pytest unit tests (no Docker/key)
    e2e.sh              # brings up compose, runs 3 examples offline, asserts 3x3 metrics
    run.sh              # runs unit tests (+ e2e behind a flag)
```

## Data flow

1. `run_eval.py` parses config (model, effort, temperature, judge model,
   `--offline`, `--param k=v`).
2. `dataset.py` loads `datasets/example/*.yaml` → cases; builds Phoenix
   `inputs=[{question}]`, `outputs=[{answer}]` (ground truth), `metadata=[...]`;
   upserts a dataset named after the directory.
3. `model.py` builds the `task(input, expected, metadata)` callable. Real:
   `litellm.completion(model, messages, temperature, max_tokens,
   reasoning_effort=…)`. Offline: deterministic answer keyed off
   `metadata.demo_quality` (good/partial/wrong) so the demo shows a score
   spread.
4. `evaluators.py` builds three `@create_evaluator(kind="LLM")` functions taking
   `(input, output, expected)`. Real: a `phoenix.evals.LLM(client="litellm")`
   judge via `generate_object` with a `{label, explanation}` schema. Offline: a
   deterministic token-overlap heuristic. Each returns `(score, label,
   explanation)`.
5. `run_experiment(dataset, task, evaluators, experiment_name,
   experiment_metadata={model, effort, …})` runs against Phoenix and persists.
6. `run_eval.py` prints a per-metric mean table and the Phoenix experiment URL.

## Comparison

Native Phoenix experiment-comparison UI (open the dataset's Experiments tab).
Each run is one experiment on the shared dataset. No bespoke diff report.

## Testing

- **Unit (no Docker, no key):** dataset loader (glob, ordering, malformed-file
  error), effort mapping, offline heuristic determinism + score bounds, config
  parsing/offline resolution.
- **e2e (`e2e.sh`, needs Docker, no key):** `docker compose up` Phoenix, run the
  3 example cases with `--offline`, assert exit 0 and 3 rows × 3 metrics. This is
  the done-criterion proof.

## Out of scope (YAGNI)

- Rubric / multi-point ground truth (single `expected` string for now).
- Bespoke local comparison report (Phoenix UI does this).
- Non-LLM metrics (exact match, embedding similarity) beyond the offline stub.
- Auto-provisioning API keys or a hosted Phoenix.
