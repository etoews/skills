"""Real-mode paths (LiteLLM task + LLM judge), exercised with mocks so no API
key or network is needed."""

import types
from typing import Any

import pytest

import evaluators
import model
from config import RunConfig


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


def _patch_completion(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch litellm.completion to capture kwargs; return the capture dict."""
    import litellm

    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> _FakeResponse:
        captured.update(kwargs)
        return _FakeResponse("MODEL OUTPUT")

    monkeypatch.setattr(litellm, "completion", fake_completion)
    return captured


def test_xhigh_anthropic_uses_output_config_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_completion(monkeypatch)
    cfg = RunConfig(
        dataset_dir="d",
        model="anthropic/claude-fable-5",
        effort="xhigh",
        system_prompt="SYS",
        params={"top_p": 0.9},
        max_tokens=1024,
        temperature=0.5,
    )
    out = model.make_task(cfg)({"question": "Q"}, metadata={})
    assert out == "MODEL OUTPUT"
    assert captured["model"] == "anthropic/claude-fable-5"
    assert captured["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Q"},
    ]
    assert captured["output_config"] == {"effort": "xhigh"}
    # Current Claude models reject explicit thinking budgets and reasoning_effort
    # is redundant when effort goes through output_config.
    assert "thinking" not in captured
    assert "reasoning_effort" not in captured
    assert captured["max_tokens"] >= 16000  # thinking counts toward max_tokens
    assert (
        captured["temperature"] == 0.5
    )  # passed; litellm drop_params handles rejection
    assert captured["top_p"] == 0.9  # --param passthrough


def test_anthropic_effort_none_sends_no_output_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_completion(monkeypatch)
    cfg = RunConfig(
        dataset_dir="d",
        model="anthropic/claude-fable-5",
        effort="none",
        max_tokens=1024,
    )
    model.make_task(cfg)({"question": "Q"})
    assert "output_config" not in captured
    assert "thinking" not in captured
    assert captured["max_tokens"] == 1024  # no headroom bump without effort


def test_high_non_anthropic_uses_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_completion(monkeypatch)
    cfg = RunConfig(
        dataset_dir="d", model="openai/gpt-5", effort="high", temperature=0.2
    )
    model.make_task(cfg)({"question": "Q"})
    assert captured["reasoning_effort"] == "high"
    assert "thinking" not in captured
    assert captured["temperature"] == 0.2


def test_none_effort_sends_no_reasoning_params(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_completion(monkeypatch)
    cfg = RunConfig(dataset_dir="d", model="openai/gpt-5", effort="none")
    model.make_task(cfg)({"question": "Q"})
    assert "reasoning_effort" not in captured
    assert "thinking" not in captured


def _fake_judge(label: str) -> types.SimpleNamespace:
    judge = types.SimpleNamespace()
    judge.generate_object = lambda prompt, schema: {
        "label": label,
        "explanation": "because",
    }
    return judge


def test_judge_positive_label_scores_one() -> None:
    corr = next(s for s in evaluators._SPECS if s.name == "correctness")
    fn = evaluators._build_eval_fn(corr, judge=_fake_judge("correct"), offline=False)
    score, label, expl = fn({"question": "q"}, "ans", {"answer": "ref"})
    assert (score, label, expl) == (1.0, "correct", "because")


def test_judge_negative_label_scores_zero() -> None:
    faith = next(s for s in evaluators._SPECS if s.name == "faithfulness")
    fn = evaluators._build_eval_fn(
        faith, judge=_fake_judge("unfaithful"), offline=False
    )
    score, label, _ = fn({"question": "q"}, "ans", {"answer": "ref"})
    assert score == 0.0 and label == "unfaithful"
