"""Run configuration + CLI parsing for the ai-eval skill.

One invocation of the skill evaluates exactly one configuration (a model, an
effort level, and any extra LLM parameters) against a dataset of prompts with
ground-truth answers. This module turns CLI arguments (and environment) into a
`RunConfig` that the rest of the pipeline consumes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field

# Portable effort levels. Anthropic models take these natively via
# `output_config.effort` (current Claude models reject explicit thinking
# budgets); other providers go through LiteLLM's cross-provider
# `reasoning_effort`, which tops out at "high". See references/providers.md.
EFFORT_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
EFFORT_TO_REASONING = {
    "none": None,
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}
ANTHROPIC_EFFORT = {
    "none": None,
    "minimal": "low",  # Anthropic's scale starts at "low"
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
}
# Headroom floor when effort is on for an Anthropic model: thinking counts
# toward max_tokens, so a small cap would truncate the answer mid-thought.
ANTHROPIC_EFFORT_MIN_MAX_TOKENS = 16_000

DEFAULT_JUDGE_MODEL = "anthropic/claude-sonnet-4-5"
DEFAULT_COLLECTOR_ENDPOINT = "http://localhost:6006"


@dataclass
class RunConfig:
    dataset_dir: str
    model: str
    effort: str = "none"
    temperature: float | None = None
    max_tokens: int = 1024
    system_prompt: str | None = None
    params: dict = field(default_factory=dict)  # extra params forwarded to LiteLLM
    judge_model: str = DEFAULT_JUDGE_MODEL
    experiment_name: str | None = None
    dataset_name: str | None = None
    collector_endpoint: str = DEFAULT_COLLECTOR_ENDPOINT
    offline: bool = False

    @property
    def reasoning_effort(self) -> str | None:
        """LiteLLM `reasoning_effort` value for this effort level (or None)."""
        return EFFORT_TO_REASONING.get(self.effort)


def _slug(text: str) -> str:
    """Filesystem/label-safe slug: lowercase, non-alphanumerics -> '-'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "run"


def _coerce(value: str):
    """Coerce a --param value: JSON if it parses (int/float/bool/null/list), else str."""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def build_config(args: argparse.Namespace) -> RunConfig:
    params: dict = {}
    for item in args.param or []:
        if "=" not in item:
            raise ValueError(f"--param must be KEY=VALUE, got {item!r}")
        key, raw = item.split("=", 1)
        params[key.strip()] = _coerce(raw)

    system_prompt = None
    if args.system_prompt_file:
        with open(args.system_prompt_file, encoding="utf-8") as f:
            system_prompt = f.read().strip()

    dataset_dir = os.path.normpath(args.dataset)
    dataset_name = args.dataset_name or _slug(os.path.basename(dataset_dir.rstrip("/")))
    experiment_name = args.experiment_name or _slug(f"{args.model}-{args.effort}")
    collector = args.collector_endpoint or os.environ.get(
        "PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_COLLECTOR_ENDPOINT
    )

    return RunConfig(
        dataset_dir=dataset_dir,
        model=args.model,
        effort=args.effort,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        system_prompt=system_prompt,
        params=params,
        judge_model=args.judge_model,
        experiment_name=experiment_name,
        dataset_name=dataset_name,
        collector_endpoint=collector,
        offline=args.offline,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_eval.py",
        description="Run one model/effort/param config against a prompt+ground-truth "
        "dataset as an Arize Phoenix experiment.",
    )
    p.add_argument("--dataset", required=True,
                   help="Directory of YAML case files (one case per file).")
    p.add_argument("--model", required=True,
                   help="LiteLLM model id under test, e.g. anthropic/claude-opus-4-8. "
                        "In --offline mode this is only a label.")
    p.add_argument("--effort", default="none", choices=EFFORT_LEVELS,
                   help="Reasoning effort (mapped per-provider). Default: none.")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=1024)
    p.add_argument("--system-prompt-file", default=None,
                   help="Optional file whose contents become the system prompt.")
    p.add_argument("--param", action="append", metavar="KEY=VALUE", default=[],
                   help="Extra LiteLLM parameter (repeatable). Value parsed as JSON if possible.")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL,
                   help=f"LLM-as-judge model. Default: {DEFAULT_JUDGE_MODEL}.")
    p.add_argument("--experiment-name", default=None,
                   help="Name for this experiment. Default: <model>-<effort>.")
    p.add_argument("--dataset-name", default=None,
                   help="Phoenix dataset name. Default: the dataset directory name.")
    p.add_argument("--collector-endpoint", default=None,
                   help="Phoenix endpoint. Default: $PHOENIX_COLLECTOR_ENDPOINT or "
                        f"{DEFAULT_COLLECTOR_ENDPOINT}.")
    p.add_argument("--offline", action="store_true",
                   help="Stub the model AND judge with deterministic heuristics (no API "
                        "calls). Proves the pipeline with no key; scores are not meaningful.")
    return p


def parse_args(argv=None) -> RunConfig:
    return build_config(build_parser().parse_args(argv))
