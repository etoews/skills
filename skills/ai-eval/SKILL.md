---
name: ai-eval
description: Use when someone wants to evaluate an LLM configuration (a new model, effort/reasoning level, temperature, or other parameters) against their own prompts with known-good "ground truth" answers, and track correctness, relevance, and faithfulness. Runs as an Arize Phoenix experiment on local Docker Compose so runs can be compared (e.g. Opus 4.8 xhigh baseline vs a newer model). Works offline (no API key) for a pipeline smoke test.
---

# ai-eval

Run a repeatable evaluation of one LLM configuration against prompts with
known-good answers, in a locally-hosted [Arize Phoenix](https://github.com/Arize-ai/phoenix).
Each run is a Phoenix **experiment** tagged with its config; Phoenix's compare UI
shows how a candidate (say, a newly released model at xhigh) stacks up against
your baseline on the prompts that matter to you, surfacing regressions and what
to change about prompting.

**Phoenix is only the harness** - it stores the dataset, orchestrates the
experiment, records scores, and provides the compare UI. It never calls an LLM.
The skill supplies the prompts+ground-truth, the model under test, and the three
LLM-as-judge graders (**correctness**, **relevance**, **faithfulness**).

Announce at start: "I'm using the ai-eval skill to run a Phoenix experiment."

## Setup (once)

All commands run from the skill directory (`skills/ai-eval/`).

```bash
docker compose up -d          # start local Phoenix -> http://localhost:6006
uv sync                       # create the Python env
```

No Docker (or can't reach Docker Hub)? Serve the same Phoenix straight from the
env instead: `uv sync && uv run phoenix serve` (also on `http://localhost:6006`).
The eval commands below are identical either way.

Provide a provider key for real runs (skip for `--offline`): put
`ANTHROPIC_API_KEY=...` (or `OPENAI_API_KEY`, `GEMINI_API_KEY`, ...) in a `.env`
file in this directory, or export it. See `references/providers.md`.

## Provide prompts + ground truth

One YAML file per case in a directory (see `datasets/example/`):

```yaml
input: |
  What is Acme Cloud's return policy for opened electronics?
expected: |
  Opened electronics: 14-day return for store credit only, all packaging
  included. No cash refunds on opened electronics.
metadata:
  category: policy
```

`input` is the prompt, `expected` is the single known-good answer. `metadata` is
optional and free-form. Point `--dataset` at the directory.

## Run

Establish a baseline, then a candidate, on the same dataset:

```bash
# baseline
uv run python scripts/run_eval.py --dataset datasets/example \
  --model anthropic/claude-opus-4-8 --effort xhigh \
  --experiment-name opus-4.8-xhigh

# candidate (a new model, same prompts + ground truth)
uv run python scripts/run_eval.py --dataset datasets/example \
  --model anthropic/claude-fable-5 --effort xhigh \
  --experiment-name fable-5-xhigh
```

Each run prints a per-metric mean and an experiment id. Open
`http://localhost:6006`, go to your dataset's **Experiments** tab, and select two
experiments to compare per-case scores and outputs side by side.

Vary anything you want to test: `--effort`, `--temperature`, `--max-tokens`,
`--system-prompt-file`, `--judge-model`, or arbitrary `--param KEY=VALUE`
(repeatable). Run `uv run python scripts/run_eval.py --help` for the full list.

## No API key? Smoke-test the pipeline offline

```bash
uv run python scripts/run_eval.py --dataset datasets/example \
  --model anthropic/claude-opus-4-8 --effort xhigh --offline \
  --experiment-name offline-demo
```

`--offline` stubs the model and judge with deterministic heuristics (no API
calls) so the whole path - Docker Phoenix, dataset, experiment, evaluators,
results - runs end to end. Scores are illustrative only.

## References

- `references/metrics.md` - what each metric means here, the judge prompts, and
  how to add or swap a metric.
- `references/providers.md` - model ids, keys, and how `effort` maps per
  provider.

## Interpreting results

- A metric drop on a case is a lead, not a verdict - open the experiment in
  Phoenix and read the candidate's output and the judge's explanation.
- Correctness down but faithfulness up usually means the answer got less
  complete, not more wrong.
- Relevance down often means a prompting/format change, not a model regression.

## Verifying a change to the skill itself

```bash
bash tests/run.sh          # pytest unit tests (no Docker, no key)
bash tests/e2e.sh          # full pipeline vs the 3 examples, offline (needs Docker)
```
