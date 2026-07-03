# Metrics

All three shipped metrics are **LLM-as-judge** and grounded on your ground-truth
answer. There is no retrieval/RAG context, so "faithfulness" is measured against
the known-good answer rather than a retrieved document. Each judge returns a
`label`, a `score` (1.0 for the positive label, 0.0 otherwise), and a short
`explanation`, all recorded on the Phoenix experiment.

| Metric | Question it answers | Positive / negative label | Grounded on |
|---|---|---|---|
| **correctness** | Does the answer match the ground truth's facts? | correct / incorrect | question + reference answer |
| **relevance** | Does the answer actually address the question? | relevant / irrelevant | question only |
| **faithfulness** | Does the answer avoid contradicting or fabricating beyond the ground truth? | faithful / unfaithful | question + reference answer |

Faithfulness replaces Phoenix's now-deprecated `HallucinationEvaluator`; the
labels are `faithful`/`unfaithful` and the metric is maximised (1.0 = faithful).

A key distinction the metrics draw: an **incomplete** answer is still *faithful*
(it invents nothing) and often still *relevant*, but it is not fully *correct*.
That is why the example `02-rotate-api-key.yaml` case (offline `partial`) scores
lower on correctness than on faithfulness.

## How the judge is called

`scripts/evaluators.py` builds one `phoenix.evals.LLM` judge (routed through
LiteLLM) and calls `judge.generate_object(prompt, schema)` with a strict
`{label, explanation}` JSON schema, so the label is always one of the two
allowed values. The prompt templates live in `evaluators.py`
(`_correctness_prompt`, `_relevance_prompt`, `_faithfulness_prompt`) - edit them
there to tune grading.

## Offline mode

`--offline` swaps the judge for a deterministic token-overlap heuristic (and the
model for a stub), so the pipeline runs with no API key. Heuristic scores are
illustrative only:

- correctness: Jaccard token overlap of answer vs reference
- relevance: fraction of question keywords the answer touches
- faithfulness: fraction of answer tokens supported by the reference

## Adding a metric

Add a `_MetricSpec` to `_SPECS` in `scripts/evaluators.py` with a name, positive
and negative labels, a prompt builder `(question, answer, reference) -> str`, and
an offline heuristic `(answer, reference, question) -> float in [0,1]`. It is
picked up automatically. To use a Phoenix built-in evaluator instead (e.g.
`phoenix.evals.metrics.FaithfulnessEvaluator`), wrap it in a
`create_evaluator(kind="LLM")` function that maps `(input, output, expected)`
onto the evaluator's input fields.
