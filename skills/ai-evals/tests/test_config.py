import pytest

import config


def _parse(*args: str) -> config.RunConfig:
    return config.parse_args(list(args))


def test_effort_maps_to_reasoning_effort() -> None:
    assert (
        _parse("--dataset", "d", "--model", "m", "--effort", "xhigh").reasoning_effort
        == "high"
    )
    assert (
        _parse("--dataset", "d", "--model", "m", "--effort", "medium").reasoning_effort
        == "medium"
    )
    assert (
        _parse("--dataset", "d", "--model", "m", "--effort", "none").reasoning_effort
        is None
    )


def test_all_effort_levels_are_mapped() -> None:
    assert set(config.EFFORT_LEVELS) == set(config.EFFORT_TO_REASONING)
    assert set(config.EFFORT_LEVELS) == set(config.ANTHROPIC_EFFORT)


def test_anthropic_effort_keeps_xhigh_and_max() -> None:
    assert config.ANTHROPIC_EFFORT["xhigh"] == "xhigh"
    assert config.ANTHROPIC_EFFORT["max"] == "max"
    # cross-provider reasoning_effort tops out at high
    assert config.EFFORT_TO_REASONING["xhigh"] == "high"


def test_param_coercion() -> None:
    cfg = _parse(
        "--dataset",
        "d",
        "--model",
        "m",
        "--param",
        "top_p=0.9",
        "--param",
        "n=2",
        "--param",
        "flag=true",
        "--param",
        "name=foo",
    )
    assert cfg.params == {"top_p": 0.9, "n": 2, "flag": True, "name": "foo"}


def test_param_requires_equals() -> None:
    with pytest.raises(ValueError):
        _parse("--dataset", "d", "--model", "m", "--param", "bogus")


def test_derived_names() -> None:
    cfg = _parse(
        "--dataset",
        "datasets/example",
        "--model",
        "anthropic/claude-opus-4-8",
        "--effort",
        "xhigh",
    )
    assert cfg.dataset_name == "example"
    assert cfg.experiment_name == "anthropic-claude-opus-4-8-xhigh"


def test_explicit_names_win() -> None:
    cfg = _parse(
        "--dataset",
        "datasets/example",
        "--model",
        "m",
        "--dataset-name",
        "prod-prompts",
        "--experiment-name",
        "run-1",
    )
    assert cfg.dataset_name == "prod-prompts"
    assert cfg.experiment_name == "run-1"


def test_offline_flag() -> None:
    assert _parse("--dataset", "d", "--model", "m", "--offline").offline is True
    assert _parse("--dataset", "d", "--model", "m").offline is False


def test_description_real_run() -> None:
    cfg = _parse(
        "--dataset",
        "d",
        "--model",
        "anthropic/claude-fable-5",
        "--effort",
        "xhigh",
        "--temperature",
        "0.2",
        "--param",
        "top_p=0.9",
    )
    assert cfg.description == (
        "anthropic/claude-fable-5 @ effort=xhigh, temp=0.2, top_p=0.9, "
        "judge=anthropic/claude-fable-5-1"
    )


def test_description_offline_flags_stub() -> None:
    cfg = _parse("--dataset", "d", "--model", "m", "--offline")
    assert "offline stub" in cfg.description
    assert "judge=" not in cfg.description


def test_judge_files_and_repetitions_parse() -> None:
    cfg = _parse(
        "--dataset", "d", "--model", "m",
        "--judge-file", "a.yaml", "--judge-file", "b.yaml",
        "--repetitions", "3",
    )  # fmt: skip

    assert cfg.judge_files == ["a.yaml", "b.yaml"]
    assert cfg.repetitions == 3


def test_defaults_to_one_repetition_and_no_judge_files() -> None:
    cfg = _parse("--dataset", "d", "--model", "m")

    assert (cfg.judge_files, cfg.repetitions) == ([], 1)


def test_repetitions_below_one_raise() -> None:
    with pytest.raises(ValueError, match="--repetitions"):
        _parse("--dataset", "d", "--model", "m", "--repetitions", "0")
