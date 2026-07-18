# ai-eval Roadmap

Build order, deliverables, and a hands-on artefact at every milestone.

For the full design rationale, see
[../../docs/superpowers/specs/2026-07-03-ai-eval-skill-design.md](../../docs/superpowers/specs/2026-07-03-ai-eval-skill-design.md).
Python work on this skill follows
[../../docs/standards/python.md](../../docs/standards/python.md).

M0 to M8 are complete: the skill runs real Phoenix experiments end to end
(validated against a real Fable 5 eval) and conforms to the repo Python standard
(ruff, ty, and a clean import model with no path shims). Carry-forward notes live
under the most recently completed milestone.

## Contents

| Milestone | Size | Status |
|-----------|------|--------|
| [M0: Scaffold + harness](#m0-scaffold--harness) | S | ✅ Complete |
| [M1: Dataset pipeline](#m1-dataset-pipeline) | M | ✅ Complete |
| [M2: Model under test](#m2-model-under-test) | M | ✅ Complete |
| [M3: Evaluators](#m3-evaluators) | M | ✅ Complete |
| [M4: Experiment runner + summary](#m4-experiment-runner--summary) | M | ✅ Complete |
| [M5: Tracing, tokens, cost](#m5-tracing-tokens-cost) | S | ✅ Complete |
| [M6: Tests](#m6-tests) | M | ✅ Complete |
| [M7: Real-run validation](#m7-real-run-validation) | S | ✅ Complete |
| [M8: Conform to the Python standard](#m8-conform-to-the-python-standard) | M | ✅ Complete |
| [M9: Discover what's new in a model and what to change about prompting](#m9-discover-whats-new-in-a-model-and-what-to-change-about-prompting) | S | ⬜ Next |
| [M10: CI](#m10-ci) | S | ⬜ Not started |
| [M11: Richer evaluation](#m11-richer-evaluation) | M | ⬜ Deferred |
| [M12: Provider breadth](#m12-provider-breadth) | S | ⬜ Deferred |

**Sizes:** S = a session. M = a few focused sessions, expect some debugging.

**Critical path:** M0 to M1 is sequential. M2 and M3 run in parallel after M1.
M4 needs M1 to M3. M5 and M6 follow M4. M7 needs a real provider key. Among the
future milestones, M10 (CI) depends on M8, which adds ruff and ty; the rest are
independently orderable. M8 is complete, so M9 and M10 are both unblocked.

---

## M0: Scaffold + harness

**Deliverables**
- [x] Skill directory with `SKILL.md` (when-to-use + quickstart) and `README.md`
  (architecture, data flow, limits).
- [x] uv-managed project: `pyproject.toml`, committed `uv.lock`,
  `.python-version` pinned to the arize-phoenix / litellm support window
  (`>=3.10,<3.13`).
- [x] `compose.yaml` for local Phoenix (`arizephoenix/phoenix:latest`, UI +
  collector on `:6006`, gRPC on `:4317`, data in a named volume).
- [x] Docker-free fallback documented: `uv run phoenix serve` on the same port.
- [x] Approved design spec committed under `docs/superpowers/specs/`.

**Hands-on artefact**
- [x] `docker compose up -d` (or `uv run phoenix serve`) then open
  `http://localhost:6006`.
- [x] `uv sync` creates the env.

**Notes**
- Docker Hub pulls can hang here; `uv run phoenix serve` is the reliable path.

---

## M1: Dataset pipeline

**Deliverables**
- [x] One-YAML-file-per-case format: `input`, `expected`, optional free-form
  `metadata`. The directory name becomes the dataset name.
- [x] `scripts/dataset.py` `load_cases()`: globs `*.yaml`/`*.yml`, stable sort by
  filename, raises `FileNotFoundError` on an empty directory and `ValueError` on
  a malformed case (not a mapping, or missing `input`/`expected`).
- [x] `sync_dataset()`: get-or-create a Phoenix dataset by name so repeated runs
  land as comparable experiments on the same dataset.
- [x] Three example cases under `datasets/example/` (the done-criterion data).

**Hands-on artefact**
- [x] `load_cases("datasets/example")` returns 3 `Case` objects in filename
  order.

---

## M2: Model under test

**Deliverables**
- [x] `scripts/model.py` `make_task()` returns the Phoenix task callable.
- [x] Real mode calls the model through **LiteLLM** (provider-agnostic), with
  `litellm.drop_params = True` so a provider silently drops params it rejects.
- [x] Portable `effort` mapping (`scripts/config.py`): Anthropic takes effort
  natively via `output_config.effort` (including `xhigh`/`max`); other providers
  go through LiteLLM's `reasoning_effort` (capped at `high`).
- [x] Anthropic effort raises a `max_tokens` floor so thinking does not truncate
  the answer.
- [x] Offline deterministic stub keyed off `metadata.demo_quality`
  (good/partial/wrong) for a no-key score spread.

**Hands-on artefact**
- [x] Offline task returns the ground truth for a `good` case and a short answer
  for a `partial` case.

---

## M3: Evaluators

**Deliverables**
- [x] Three LLM-as-judge metrics in `scripts/evaluators.py`, all grounded on the
  ground-truth answer (no RAG context):
  - **correctness** (does the answer match the reference's facts?)
  - **relevance** (does it address the question?)
  - **faithfulness** (does it avoid claims beyond or against the reference? -
    replaces the deprecated Hallucination metric).
- [x] Real mode judges with a `phoenix.evals.LLM` (routed through LiteLLM) using
  a `{label, explanation}` structured-output schema.
- [x] Offline mode uses deterministic token-overlap heuristics per metric.
- [x] Each metric returns `(score, label, explanation)`.

**Hands-on artefact**
- [x] Offline evaluators return bounded, deterministic scores for the same
  input across repeated runs.

---

## M4: Experiment runner + summary

**Deliverables**
- [x] `scripts/run_eval.py` CLI: parse config, load cases, sync dataset, build
  task + evaluators, call Phoenix `run_experiment`, print the summary.
- [x] `experiment_metadata` tags every run with its config (model, effort,
  temperature, offline, judge model, arbitrary `param.*`).
- [x] Per-metric mean summary printed, plus the Phoenix compare link.
- [x] Full flag surface: `--effort`, `--temperature`, `--max-tokens`,
  `--system-prompt-file`, `--judge-model`, repeatable `--param KEY=VALUE`,
  `--experiment-name`, `--dataset-name`, `--collector-endpoint`, `--offline`.

**Hands-on artefact**
- [x] Two `--offline` runs on `datasets/example` appear as two experiments in
  the dataset's Experiments tab, comparable side by side.

---

## M5: Tracing, tokens, cost

**Deliverables**
- [x] Real runs instrument LiteLLM with OpenInference, exporting to Phoenix, so
  each model and judge call emits token counts.
- [x] Phoenix experiment table fills its "total tokens" and "total cost" columns
  (cost also needs the model in Phoenix's price table under Settings > Models).
- [x] One-line experiment description shown in the experiments table.

**Hands-on artefact**
- [x] A real run shows non-zero total tokens in the Phoenix experiments table.

**Notes**
- Offline runs make no LLM calls, so they show no tokens or cost by design.

---

## M6: Tests

**Deliverables**
- [x] pytest unit suite (`tests/`, no Docker, no key): dataset loader (glob,
  ordering, malformed-file errors), effort mapping, offline heuristic
  determinism and bounds, config parsing and offline resolution.
- [x] `tests/run.sh` runs the unit suite; `tests/e2e.sh` brings up Phoenix, runs
  the 3 examples offline, and asserts 3 cases x 3 metrics.
- [x] `[tool.pytest.ini_options]` with `testpaths = ["tests"]`.

**Hands-on artefact**
- [x] `bash tests/run.sh` passes with no Docker and no key.

---

## M7: Real-run validation

**Deliverables**
- [x] First real run against a live provider key, no `--offline`.
- [x] Effort mapping corrected for current Claude models: they reject explicit
  extended-thinking budgets, so effort is sent via `output_config.effort` only.
  Exactly the model-API drift this skill exists to surface.
- [x] Verified end to end with a real Fable 5 eval; experiment description,
  total tokens, and total cost populated.

**Hands-on artefact**
- [x] A real experiment on `datasets/example` records per-metric means and
  tokens/cost in Phoenix.

---

## M8: Conform to the Python standard

Bring the skill up to [../../docs/standards/python.md](../../docs/standards/python.md).

**Deliverables**
- [x] Add ruff (config + `--dev` dep). Adopt the standard rule selection
  (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`) and the tests per-file ignores
  (`S101`, `D`). `ruff check` and `ruff format --check` run clean.
- [x] Resolve the import model so the `sys.path.insert` hack and every
  `# noqa: E402` disappear. Resolved with pytest `pythonpath = ["scripts"]` (which
  retired `tests/conftest.py`) plus `[tool.ty.environment] root = ["scripts"]`;
  the in-place entry point relies on Python's automatic `sys.path[0]`, so the
  flat `scripts/` layout the standard prescribes is kept.
- [x] Add ty (config + `--dev` dep). Complete the type coverage: full signatures
  on every function in `scripts/` and `tests/` (including `-> None`), replacing
  loose `Any`/untyped parameters where practical. `ty check` runs clean.
- [x] Tighten `[tool.pytest.ini_options]` to the standard
  `addopts = "-ra --strict-markers --strict-config"`.

**Hands-on artefact**
- [x] `uv run ruff check`, `uv run ruff format --check`, and `uv run ty check`
  all pass, and `bash tests/run.sh` still passes.

### Carry-forward

- **M10**: CI is now unblocked (ruff and ty are in place). The GitHub Actions
  workflow runs `uv sync --locked`, `ruff check`, `ruff format --check`,
  `ty check`, and the unit suite.
- **M12**: the cross-provider effort mapping is approximate (non-Anthropic
  providers cap at `high`). Compare within a provider for the cleanest signal
  until a second provider is validated.
- ty is pre-1.0 (pinned `>=0.0.60`); it ran clean here with no mypy fallback
  needed. External Phoenix/LiteLLM objects (`client`, `judge`, dataset, evaluator
  list) are annotated `Any` at the boundary by design.

---

## M9: Discover what's new in a model and what to change about prompting

The skill's reason to exist (design spec, Purpose): run a baseline and a
candidate on your own prompts, then read the comparison to learn what the new
model does differently and which prompts need to change. Uses the native Phoenix
compare UI, no bespoke diff report (a load-bearing design decision).

**Deliverables**
- [ ] A real baseline experiment on a real dataset (your own prompts + ground
  truth, not only `datasets/example`), tagged with its config.
- [ ] A candidate experiment: a newer or different model on the same dataset and
  ground truth, with `--judge-model` pinned so the grader is held constant.
- [ ] A read of the Phoenix compare view that separates the two signals:
  (a) **what changed in the model** (per-case score deltas, output style,
  verbosity, refusals, format drift, and the model-API drift the skill exists to
  surface) versus (b) **what to change about prompting** (which regressions are
  prompt-fixable, and the specific edit).
- [ ] At least one prompt change (via `--system-prompt-file` or reworded cases)
  re-run as a third experiment that recovers a regressed metric.
- [ ] The discovery loop written up in `README.md` / `SKILL.md` so it is
  repeatable, not a one-off (extends the existing "Interpreting results" notes).

**Hands-on artefact**
- [ ] Three real experiments on one dataset (baseline, candidate, candidate +
  revised prompt) compared in Phoenix, with the prompt revision measurably
  closing an identified regression.

---

## M10: CI

**Deliverables**
- [ ] GitHub Actions workflow scoped to the `ai-eval` path: `uv sync --locked`,
  `ruff check`, `ruff format --check`, `ty check`, `pytest` (unit suite only, no
  Docker or key in CI).
- [ ] Pin `astral-sh/setup-uv` to a major tag; bump deliberately.

**Hands-on artefact**
- [ ] A PR touching `skills/ai-eval/` runs the checks and blocks on failure.

---

## M11: Richer evaluation

Promote items from the design's YAGNI list as real need appears.

**Deliverables**
- [ ] Rubric / multi-point ground truth (beyond a single `expected` string).
- [ ] Additional or swappable LLM-as-judge metrics (the evaluator list is
  already extensible).
- [ ] Optional non-LLM metrics (exact match, embedding similarity) for cases
  where a deterministic signal is enough.

**Hands-on artefact**
- [ ] A rubric-scored case reports per-point results in Phoenix.

---

## M12: Provider breadth

**Deliverables**
- [ ] Validate a real end-to-end run on a second provider (OpenAI or Gemini),
  not just Anthropic.
- [ ] Sharpen `references/providers.md` on how `effort` maps per provider, based
  on what the real run surfaces.

**Hands-on artefact**
- [ ] A non-Anthropic real run records per-metric means and tokens in Phoenix.
