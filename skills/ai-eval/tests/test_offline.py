"""Offline stub model + heuristic judge: determinism and bounds."""

from typing import Any

import evaluators
import model
from config import RunConfig


def _cfg(**kw: Any) -> RunConfig:
    return RunConfig(dataset_dir="d", model="anthropic/claude-x", offline=True, **kw)


REF = {"answer": "Paris is the capital of France. It has about 2 million people."}
Q = {"question": "What is the capital of France?"}


def test_offline_task_quality_levels_are_distinct_and_deterministic() -> None:
    task = model.make_task(_cfg())
    good = task(Q, expected=REF, metadata={"demo_quality": "good"})
    partial = task(Q, expected=REF, metadata={"demo_quality": "partial"})
    wrong = task(Q, expected=REF, metadata={"demo_quality": "wrong"})
    assert good == REF["answer"]
    assert partial and partial != good and good.startswith(partial)
    assert wrong != good
    # deterministic
    assert task(Q, expected=REF, metadata={"demo_quality": "partial"}) == partial


def test_offline_task_defaults_to_good() -> None:
    task = model.make_task(_cfg())
    assert task(Q, expected=REF, metadata={}) == REF["answer"]


def _run_metric(
    spec: evaluators._MetricSpec,
    answer: str,
    reference: str = REF["answer"],
    question: str = Q["question"],
) -> tuple[float, str, str]:
    fn = evaluators._build_eval_fn(spec, judge=None, offline=True)
    return fn({"question": question}, answer, {"answer": reference})


def test_heuristics_are_bounded_and_deterministic() -> None:
    for spec in evaluators._SPECS:
        for answer in [REF["answer"], "totally unrelated text 42", "", "Paris"]:
            score, label, _ = _run_metric(spec, answer)
            assert 0.0 <= score <= 1.0, (spec.name, answer, score)
            assert label in (spec.positive, spec.negative)
            assert _run_metric(spec, answer)[0] == score  # deterministic


def test_perfect_match_scores_positive() -> None:
    for spec in evaluators._SPECS:
        score, label, _ = _run_metric(spec, REF["answer"])
        assert label == spec.positive, spec.name
        if spec.name in ("correctness", "faithfulness"):
            assert score == 1.0, spec.name


def test_wrong_answer_scores_low_on_correctness() -> None:
    corr = next(s for s in evaluators._SPECS if s.name == "correctness")
    score, label, _ = _run_metric(
        corr, "I'm not certain, but I believe the answer is 42."
    )
    assert label == corr.negative
    assert score < 0.5


def test_partial_answer_faithful_but_not_fully_correct() -> None:
    corr = next(s for s in evaluators._SPECS if s.name == "correctness")
    faith = next(s for s in evaluators._SPECS if s.name == "faithfulness")
    partial = "Paris is the capital of France."
    assert _run_metric(faith, partial)[0] >= _run_metric(corr, partial)[0]
