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

`--effort` is a portable knob with a per-provider mapping:

| `--effort` | Anthropic (`output_config.effort`) | Others (LiteLLM `reasoning_effort`) |
|---|---|---|
| none | (unset) | (unset) |
| minimal | low | minimal |
| low | low | low |
| medium | medium | medium |
| high | high | high |
| xhigh | xhigh | high |
| max | max | high |

Anthropic models take effort natively via `output_config.effort` (including
`xhigh` and `max`). Current Claude models (Fable 5, Opus 4.7/4.8, Sonnet 5)
**reject** explicit extended-thinking budgets (`thinking: {type: enabled,
budget_tokens: N}` returns a 400) and also reject `temperature`, so the skill
never sends a thinking budget and relies on LiteLLM's `drop_params=True` to
drop `temperature` where it is unsupported. Because thinking counts toward
`max_tokens` on these models, the skill raises `max_tokens` to at least 16000
whenever effort is set on an Anthropic model.

Other providers go through LiteLLM's cross-provider `reasoning_effort`, which
tops out at `high` - so `xhigh`/`max` behave like `high` there.

Because `effort` semantics differ across providers, comparisons are cleanest
*within* one provider (e.g. Opus 4.8 xhigh vs a newer Claude at xhigh).

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
