"""Load YAML case files and turn them into a Phoenix dataset.

A "case" is one prompt plus its known-good ("ground truth") answer, stored as a
single YAML file:

    input: |
      What is our refund policy for opened electronics?
    expected: |
      Opened electronics: 14-day return for store credit only ...
    metadata:
      category: policy

The directory of cases becomes a Phoenix dataset whose `inputs` hold the
questions and `outputs` hold the ground-truth answers.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import yaml


@dataclass
class Case:
    name: str  # filename stem, used as a stable case id
    input: str  # the prompt / question
    expected: str  # the ground-truth answer
    metadata: dict = field(default_factory=dict)


def load_cases(dataset_dir: str) -> list[Case]:
    """Load every *.yaml/*.yml file in `dataset_dir`, sorted by filename.

    Raises FileNotFoundError if the directory has no case files, and ValueError
    for a malformed case (not a mapping, or missing `input`/`expected`).
    """
    paths = sorted(
        glob.glob(os.path.join(dataset_dir, "*.yaml"))
        + glob.glob(os.path.join(dataset_dir, "*.yml"))
    )
    if not paths:
        raise FileNotFoundError(f"No .yaml/.yml case files found in {dataset_dir!r}")

    cases: list[Case] = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: expected a YAML mapping, got {type(doc).__name__}")
        missing = [k for k in ("input", "expected") if not doc.get(k)]
        if missing:
            raise ValueError(f"{path}: missing required key(s): {', '.join(missing)}")
        cases.append(
            Case(
                name=os.path.splitext(os.path.basename(path))[0],
                input=str(doc["input"]).strip(),
                expected=str(doc["expected"]).strip(),
                metadata=dict(doc.get("metadata") or {}),
            )
        )
    return cases


def sync_dataset(client, name: str, cases: list[Case]):
    """Get-or-create a Phoenix dataset named `name` from `cases`.

    Reuses an existing dataset with the same name so repeated runs land as
    comparable experiments on the same dataset. To evaluate a changed set of
    cases, use a new --dataset-name.
    """
    try:
        existing = client.datasets.get_dataset(dataset=name)
        if existing is not None:
            return existing
    except Exception:
        pass  # not found (or server has none yet) -> create below

    inputs = [{"question": c.input} for c in cases]
    outputs = [{"answer": c.expected} for c in cases]
    metadata = [{**c.metadata, "case": c.name} for c in cases]
    return client.datasets.create_dataset(
        name=name,
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
        dataset_description="ai-eval prompts with ground-truth answers",
    )
