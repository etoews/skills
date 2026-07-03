"""ai-eval entrypoint: run one config against a prompt+ground-truth dataset.

    uv run python scripts/run_eval.py \
        --dataset datasets/example \
        --model anthropic/claude-opus-4-8 --effort xhigh \
        --experiment-name "opus-4.8-xhigh"

Flow: load config -> load YAML cases -> get-or-create Phoenix dataset ->
run_experiment (task = model under test, evaluators = the three judges) ->
print a per-metric summary. Add --offline to run with deterministic stubs and
no API key.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import parse_args  # noqa: E402
from dataset import load_cases, sync_dataset  # noqa: E402
from evaluators import make_evaluators  # noqa: E402
from model import make_task  # noqa: E402


def _get(obj: Any, key: str, default=None):
    """Attribute-or-key access, tolerant of dataclass vs dict result shapes."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_score(result: Any) -> Optional[float]:
    score = _get(result, "score")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


def _print_summary(ran: Any, cfg, n_cases: int) -> None:
    eval_runs = _get(ran, "evaluation_runs", []) or []
    scores: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    for r in eval_runs:
        name = _get(r, "name")
        if not name:
            continue
        if _get(r, "error"):
            errors[name] += 1
            continue
        score = _extract_score(_get(r, "result"))
        if score is not None:
            scores[name].append(score)

    print("\n=== ai-eval summary ===")
    print(f"experiment : {cfg.experiment_name}")
    print(f"dataset    : {cfg.dataset_name}  ({n_cases} cases)")
    print(f"model      : {cfg.model}   effort: {cfg.effort}"
          + ("   [OFFLINE STUB - scores not meaningful]" if cfg.offline else ""))
    if not scores:
        print("  (no evaluator scores recorded)")
    for name in sorted(scores):
        vals = scores[name]
        mean = sum(vals) / len(vals)
        note = f"   {errors[name]} error(s)" if errors.get(name) else ""
        print(f"  {name:<14} mean={mean:.3f}  (n={len(vals)}){note}")

    exp_id = _get(ran, "experiment_id")
    print(f"\nCompare experiments in Phoenix: {cfg.collector_endpoint}"
          "  (open your dataset's Experiments tab)")
    if exp_id:
        print(f"experiment_id: {exp_id}")


def main(argv=None) -> int:
    load_dotenv()
    cfg = parse_args(argv)

    cases = load_cases(cfg.dataset_dir)
    print(f"Loaded {len(cases)} case(s) from {cfg.dataset_dir}")

    from phoenix.client import Client

    client = Client(base_url=cfg.collector_endpoint)
    dataset = sync_dataset(client, cfg.dataset_name, cases)
    print(f"Dataset ready: {cfg.dataset_name!r}")

    task = make_task(cfg)
    evaluators = make_evaluators(cfg)

    from phoenix.client.experiments import run_experiment

    mode = "OFFLINE stub model + judge" if cfg.offline else f"{cfg.model} / effort={cfg.effort}"
    print(f"Running experiment {cfg.experiment_name!r}  [{mode}] ...")
    ran = run_experiment(
        dataset=dataset,
        task=task,
        evaluators=evaluators,
        experiment_name=cfg.experiment_name,
        experiment_metadata={
            "model": cfg.model,
            "effort": cfg.effort,
            "temperature": cfg.temperature,
            "offline": cfg.offline,
            "judge_model": None if cfg.offline else cfg.judge_model,
            **{f"param.{k}": v for k, v in cfg.params.items()},
        },
        print_summary=True,
        client=client,
    )

    _print_summary(ran, cfg, len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
