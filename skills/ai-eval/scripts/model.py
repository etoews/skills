"""The task under evaluation: run the model-under-test on each prompt.

`make_task` returns a callable that Phoenix's `run_experiment` invokes once per
dataset example. Phoenix binds arguments by name, so the callable may accept any
of `input`, `expected`, `metadata`, `example`.

Real mode calls the model through LiteLLM (provider-agnostic). Offline mode
returns a deterministic stub answer so the whole pipeline runs with no API key;
the stub's quality is keyed off each case's `metadata.demo_quality`
(good/partial/wrong) so the demo shows a spread of scores.
"""

from __future__ import annotations

from typing import Any, Callable

from config import ANTHROPIC_XHIGH_BUDGET_TOKENS, RunConfig


def _expected_text(expected: Any) -> str:
    if isinstance(expected, dict):
        return str(expected.get("answer", "")).strip()
    return str(expected or "").strip()


def _question_text(input: Any) -> str:
    if isinstance(input, dict):
        return str(input.get("question", "")).strip()
    return str(input or "").strip()


def make_task(cfg: RunConfig) -> Callable:
    return _make_offline_task() if cfg.offline else _make_litellm_task(cfg)


def _make_litellm_task(cfg: RunConfig) -> Callable:
    import litellm

    litellm.drop_params = True  # drop params a given provider doesn't support

    def task(input: Any, metadata: dict | None = None) -> str:
        messages: list[dict[str, str]] = []
        if cfg.system_prompt:
            messages.append({"role": "system", "content": cfg.system_prompt})
        messages.append({"role": "user", "content": _question_text(input)})

        kwargs: dict[str, Any] = dict(cfg.params)
        kwargs["max_tokens"] = cfg.max_tokens
        if cfg.temperature is not None:
            kwargs["temperature"] = cfg.temperature
        if cfg.reasoning_effort:
            kwargs["reasoning_effort"] = cfg.reasoning_effort

        # xhigh on Anthropic: use an explicit extended-thinking budget. Thinking
        # requires the default temperature and max_tokens greater than the budget.
        if cfg.effort == "xhigh" and cfg.model.startswith("anthropic"):
            budget = ANTHROPIC_XHIGH_BUDGET_TOKENS
            kwargs.pop("reasoning_effort", None)
            kwargs.pop("temperature", None)
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
            kwargs["max_tokens"] = max(cfg.max_tokens, budget + 4096)

        resp = litellm.completion(model=cfg.model, messages=messages, **kwargs)
        return (resp.choices[0].message.content or "").strip()

    return task


def _make_offline_task() -> Callable:
    def task(input: Any, expected: Any = None, metadata: dict | None = None) -> str:
        quality = str((metadata or {}).get("demo_quality", "good")).lower()
        reference = _expected_text(expected)
        if quality == "wrong":
            return "I'm not certain, but I believe the answer is 42."
        if quality == "partial":
            first = reference.split(". ")[0].strip()
            return first or reference[: max(1, len(reference) // 2)]
        return reference  # "good": echo the ground truth

    return task
