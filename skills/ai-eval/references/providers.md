# Providers, models, and effort

The model under test is invoked through [LiteLLM](https://docs.litellm.ai/), so
`--model` uses LiteLLM's `provider/model` ids, e.g.:

| Provider | `--model` example | Key env var |
|---|---|---|
| Anthropic | `anthropic/claude-opus-4-8` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-5` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-2.5-pro` | `GEMINI_API_KEY` |
| Bedrock | `bedrock/anthropic.claude-...` | AWS credentials |

Put keys in a `.env` file in the skill directory (git-ignored) or export them;
`run_eval.py` loads `.env` automatically. The same applies to `--judge-model`
(default `anthropic/claude-sonnet-4-5`).

## Effort

`--effort` is a portable knob, mapped to LiteLLM's `reasoning_effort`:

| `--effort` | LiteLLM `reasoning_effort` | Notes |
|---|---|---|
| none | (unset) | no reasoning params sent |
| minimal | minimal | |
| low | low | |
| medium | medium | |
| high | high | |
| xhigh | high (+ thinking budget on Anthropic) | see below |

`xhigh` has no LiteLLM equivalent. On Anthropic models it instead sends an
explicit extended-thinking budget (`thinking={type: enabled, budget_tokens:
32000}`), drops `temperature` (thinking requires the default), and raises
`max_tokens` above the budget. On other providers `xhigh` behaves like `high`.

Because `effort` semantics differ across providers, comparisons are cleanest
*within* one provider (e.g. Opus 4.8 xhigh vs a newer Claude at xhigh). LiteLLM
runs with `drop_params=True`, so a param a provider does not support is dropped
rather than erroring.

## Other LLM parameters

Pass anything else straight through to LiteLLM with repeatable `--param KEY=VALUE`
(value parsed as JSON when possible), e.g.:

```
--param top_p=0.9 --param stop='["\n\n"]'
```

## Adding a provider

No code change is usually needed - if LiteLLM supports the provider and the key
is set, `--model provider/model` works. To customise how a provider maps effort,
edit `EFFORT_TO_REASONING` / the `xhigh` branch in `scripts/config.py` and
`scripts/model.py`.
