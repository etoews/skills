"""Extra judges loaded from YAML with --judge-file."""

from pathlib import Path

import pytest

import evaluators
from config import RunConfig

_VALID = """\
name: style
positive: pass
negative: fail
prompt: |
  Q={question} A={answer} R={reference} {literal braces}
"""


def _write(tmp_path: Path, text: str, name: str = "judge.yaml") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_prompt_fills_placeholders_and_keeps_other_braces(tmp_path: Path) -> None:
    spec = evaluators.load_judge_file(_write(tmp_path, _VALID))

    prompt = spec.prompt("q1", "a1", "r1")

    assert (spec.name, spec.positive, spec.negative) == ("style", "pass", "fail")
    assert prompt.strip() == "Q=q1 A=a1 R=r1 {literal braces}"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- a list\n", "expected a YAML mapping"),
        ("name: x\npositive: p\nnegative: n\n", "missing required key(s): prompt"),
        ("name: x\npositive: p\nnegative: n\nprompt: no slot\n", "{answer}"),
        (
            "name: correctness\npositive: p\nnegative: n\nprompt: '{answer}'\n",
            "built-in metric name",
        ),
    ],
)
def test_invalid_judge_file_raises(tmp_path: Path, text: str, message: str) -> None:
    path = _write(tmp_path, text)

    with pytest.raises(ValueError) as err:
        evaluators.load_judge_file(path)

    assert message in str(err.value)


def test_make_evaluators_adds_judge_files(tmp_path: Path) -> None:
    cfg = RunConfig(
        dataset_dir="d", model="m", offline=True, judge_files=[_write(tmp_path, _VALID)]
    )

    evs = evaluators.make_evaluators(cfg)

    assert len(evs) == len(evaluators._SPECS) + 1


def test_duplicate_judge_names_raise(tmp_path: Path) -> None:
    paths = [_write(tmp_path, _VALID, f"j{i}.yaml") for i in range(2)]
    cfg = RunConfig(dataset_dir="d", model="m", offline=True, judge_files=paths)

    with pytest.raises(ValueError, match="duplicate judge name"):
        evaluators.make_evaluators(cfg)


def test_judge_file_scores_with_judge_labels(tmp_path: Path) -> None:
    spec = evaluators.load_judge_file(_write(tmp_path, _VALID))

    class _Judge:
        def generate_object(self, prompt: str, schema: dict) -> dict:
            assert schema["properties"]["label"]["enum"] == ["pass", "fail"]
            return {"label": "fail", "explanation": "long sentences"}

    fn = evaluators._build_eval_fn(spec, judge=_Judge(), offline=False)
    score, label, expl = fn({"question": "q"}, "ans", {"answer": "ref"})

    assert (score, label, expl) == (0.0, "fail", "long sentences")
