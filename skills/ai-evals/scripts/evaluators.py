"""LLM-as-judge evaluators, scored against the ground-truth answer.

Three metrics, all grounded on the known-good answer (there is no retrieval/RAG
context here):

  correctness  - does the answer match the ground truth's facts?
  relevance    - does the answer actually address the question?
  faithfulness - does the answer avoid claims that contradict or go beyond the
                 ground truth? (Replaces the deprecated Hallucination metric.)

Each evaluator is a Phoenix experiment evaluator (`create_evaluator(kind="LLM")`)
taking `(input, output, expected)` and returning `(score, label, explanation)`.

Extra binary judges (for example a style rubric) load from YAML files passed with
`--judge-file`; see `load_judge_file`.

Real mode judges with a `phoenix.evals.LLM` (routed through LiteLLM) using
structured output. Offline mode uses a deterministic token-overlap heuristic so
the pipeline runs with no API key; heuristic scores are illustrative, not real.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import yaml
from phoenix.client.experiments import create_evaluator

from config import RunConfig

logger = logging.getLogger(__name__)

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
    _MetricSpec(
        "relevance", "relevant", "irrelevant", _relevance_prompt, _question_coverage
    ),
    _MetricSpec(
        "faithfulness",
        "faithful",
        "unfaithful",
        _faithfulness_prompt,
        _reference_precision,
    ),
]


_PLACEHOLDERS = ("{question}", "{answer}", "{reference}")


def load_judge_file(path: str) -> _MetricSpec:
    """Load an extra binary LLM judge from a YAML file.

    The file needs `name`, `positive`, `negative` and `prompt`. The prompt must
    contain `{answer}` and may contain `{question}` and `{reference}`; those
    placeholders are replaced literally, so other braces in the rubric are safe.
    Offline mode scores these judges with the correctness heuristic.

    Raises:
        ValueError: the file is not a mapping, lacks a key, has no `{answer}`
            placeholder, or reuses a built-in metric name.
    """
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a YAML mapping, got {type(doc).__name__}")
    keys = ("name", "positive", "negative", "prompt")
    missing = [k for k in keys if not str(doc.get(k) or "").strip()]
    if missing:
        raise ValueError(f"{path}: missing required key(s): {', '.join(missing)}")
    name, positive, negative, template = (str(doc[k]).strip() for k in keys)
    if "{answer}" not in template:
        raise ValueError(f"{path}: prompt must contain the {{answer}} placeholder")
    if name in {spec.name for spec in _SPECS}:
        raise ValueError(f"{path}: {name!r} is a built-in metric name")

    def prompt(question: str, answer: str, reference: str) -> str:
        out = template
        for placeholder, value in zip(
            _PLACEHOLDERS, (question, answer, reference), strict=True
        ):
            out = out.replace(placeholder, value)
        return out

    logger.info("loaded judge %r from %s", name, path)
    return _MetricSpec(name, positive, negative, prompt, _jaccard)


def _schema(positive: str, negative: str) -> dict[str, Any]:
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


def _build_eval_fn(
    spec: _MetricSpec, judge: Any, offline: bool
) -> Callable[..., tuple[float, str, str]]:
    def _eval(input: Any, output: Any, expected: Any) -> tuple[float, str, str]:
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


def make_evaluators(cfg: RunConfig) -> list[Any]:
    judge = None
    if not cfg.offline:
        from phoenix.evals import LLM

        provider, model = _split_judge_model(cfg.judge_model)
        judge = LLM(provider=provider, model=model, client="litellm")

    specs = _SPECS + [load_judge_file(path) for path in cfg.judge_files]
    names = [spec.name for spec in specs]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"duplicate judge name(s): {', '.join(duplicates)}")

    evaluators: list[Any] = []
    for spec in specs:
        fn = _build_eval_fn(spec, judge, cfg.offline)
        evaluators.append(create_evaluator(kind="LLM", name=spec.name)(fn))
    return evaluators
