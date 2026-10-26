from pathlib import Path

import pytest

from dataset import Case, load_cases


def _write(dir: Path, name: str, text: str) -> Path:
    p = dir / name
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_cases_sorted_by_filename(tmp_path: Path) -> None:
    _write(tmp_path, "02-b.yaml", "input: q2\nexpected: a2\n")
    _write(tmp_path, "01-a.yaml", "input: q1\nexpected: a1\nmetadata: {category: x}\n")
    cases = load_cases(str(tmp_path))
    assert [c.name for c in cases] == ["01-a", "02-b"]
    assert cases[0] == Case(
        name="01-a", input="q1", expected="a1", metadata={"category": "x"}
    )
    assert cases[1].metadata == {}


def test_picks_up_yml_extension(tmp_path: Path) -> None:
    _write(tmp_path, "case.yml", "input: q\nexpected: a\n")
    assert len(load_cases(str(tmp_path))) == 1


def test_empty_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_cases(str(tmp_path))


def test_missing_expected_raises(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", "input: q\n")
    with pytest.raises(ValueError, match="expected"):
        load_cases(str(tmp_path))


def test_non_mapping_raises(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", "- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="mapping"):
        load_cases(str(tmp_path))
