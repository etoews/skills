"""LLM-as-judge evaluators, scored against the ground-truth answer.

Three metrics, all grounded on the known-good answer (there is no retrieval/RAG
context here):

  correctness  - does the answer match the ground truth's facts?
  relevance    - does the answer actually address the question?
  faithfulness - does the answer avoid claims that contradict or go beyond the
                 ground truth? (Replaces the deprecated Hallucination metric.)

Each evaluator is a Phoenix experiment evaluator (`create_evaluator(kind="LLM")`)
taking `(input, output, expected)` and returning `(score, label, explanation)`.

Real mode judges with a `phoenix.evals.LLM` (routed through LiteLLM) using
structured output. Offline mode uses a deterministic token-overlap heuristic so
the pipeline runs with no API key; heuristic scores are illustrative, not real.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from phoenix.client.experiments import create_evaluator

from config import RunConfig


# --- text helpers -----------------------------------------------------------

def _field(value: Any, key: str) -> str:
    if isinstance(value, dict):
        return str(value.get(key, "")).strip()
    return str(value or "").strip()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _jaccard(answer: str, reference: str, question: str) -> float:
    """Correctness heuristic: token overlap between answer and reference."""
    a, b = set(_tokens(answer)), set(_tokens(reference))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _question_coverage(answer: str, reference: str, question: str) -> float:
    """Relevance heuristic: fraction of question keywords the answer touches."""
    a, q = set(_tokens(answer)), set(_tokens(question))
    if not a or not q:
        return 0.0
    return len(a & q) / len(q)


def _reference_precision(answer: str, reference: str, question: str) -> float:
    """Faithfulness heuristic: fraction of answer tokens supported by reference."""
    a, b = _tokens(answer), set(_tokens(reference))
    if not a:
        return 0.0
    return sum(1 for t in a if t in b) / len(a)


# --- judge prompts ----------------------------------------------------------

def _correctness_prompt(question: str, answer: str, reference: str) -> str:
    return (
        "You are grading whether a CANDIDATE answer is correct, using the "
        "REFERENCE (ground-truth) answer as the source of truth.\n\n"
        f"[Question]\n{question}\n\n[Reference answer]\n{reference}\n\n"
        f"[Candidate answer]\n{answer}\n\n"
        "Is the candidate factually consistent with the reference and does it "
        "answer the question correctly? Minor wording differences are fine. "
        "Label 'correct' or 'incorrect' and explain briefly."
    )


def _relevance_prompt(question: str, answer: str, reference: str) -> str:
    return (
        "You are grading whether a CANDIDATE answer is relevant to the QUESTION "
        "- i.e. it actually addresses what was asked. Judge relevance only, not "
        "correctness.\n\n"
        f"[Question]\n{question}\n\n[Candidate answer]\n{answer}\n\n"
        "Label 'relevant' or 'irrelevant' and explain briefly."
    )


def _faithfulness_prompt(question: str, answer: str, reference: str) -> str:
    return (
        "You are checking a CANDIDATE answer for faithfulness to the REFERENCE "
        "(ground-truth) answer. The candidate is 'unfaithful' if it asserts "
        "claims that contradict the reference or fabricates specifics the "
        "reference does not support (hallucination). Being incomplete is still "
        "faithful.\n\n"
        f"[Question]\n{question}\n\n[Reference answer]\n{reference}\n\n"
        f"[Candidate answer]\n{answer}\n\n"
        "Label 'faithful' or 'unfaithful' and explain briefly."
    )


# --- evaluator assembly -----------------------------------------------------

@dataclass
class _MetricSpec:
    name: str
    positive: str  # label meaning score 1.0
    negative: str  # label meaning score 0.0
    prompt: Callable[[str, str, str], str]
    heuristic: Callable[[str, str, str], float]


_SPECS = [
    _MetricSpec("correctness", "correct", "incorrect", _correctness_prompt, _jaccard),
    _MetricSpec("relevance", "relevant", "irrelevant", _relevance_prompt, _question_coverage),
    _MetricSpec("faithfulness", "faithful", "unfaithful", _faithfulness_prompt, _reference_precision),
]


def _schema(positive: str, negative: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": [positive, negative]},
            "explanation": {"type": "string"},
        },
        "required": ["label", "explanation"],
    }


def _split_judge_model(judge_model: str) -> tuple[str, str]:
    """Split a LiteLLM-style id into (provider, model); default provider anthropic."""
    if "/" in judge_model:
        provider, model = judge_model.split("/", 1)
        return provider, model
    return "anthropic", judge_model


def _build_eval_fn(spec: _MetricSpec, judge, offline: bool) -> Callable:
    def _eval(input: Any, output: Any, expected: Any):
        question = _field(input, "question")
        answer = output if isinstance(output, str) else _field(output, "answer")
        reference = _field(expected, "answer")

        if offline or judge is None:
            score = spec.heuristic(answer, reference, question)
            label = spec.positive if score >= 0.5 else spec.negative
            return (round(score, 3), label, f"[offline heuristic] overlap={score:.2f}")

        result = judge.generate_object(
            prompt=spec.prompt(question, answer, reference),
            schema=_schema(spec.positive, spec.negative),
        )
        label = str(result.get("label", spec.negative))
        explanation = str(result.get("explanation", ""))
        score = 1.0 if label == spec.positive else 0.0
        return (score, label, explanation)

    return _eval


def make_evaluators(cfg: RunConfig) -> list:
    judge = None
    if not cfg.offline:
        from phoenix.evals import LLM

        provider, model = _split_judge_model(cfg.judge_model)
        judge = LLM(provider=provider, model=model, client="litellm")

    evaluators = []
    for spec in _SPECS:
        fn = _build_eval_fn(spec, judge, cfg.offline)
        evaluators.append(create_evaluator(kind="LLM", name=spec.name)(fn))
    return evaluators
