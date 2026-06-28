#!/usr/bin/env bash
# Headless security review: build the request, invoke the Claude CLI, and
# extract a validated verdict from its output.
#
# Invocation (review_run) is a thin, configurable wrapper so it can be tuned
# from the spike and stubbed in tests via $CLAUDE_BIN. The parsing helpers
# (review_extract_verdict, review_max_severity) are pure and unit-tested.

# review_schema : the JSON schema the review is forced to emit (--json-schema).
review_schema() {
  cat <<'JSON'
{"type":"object","additionalProperties":false,
 "properties":{
   "max_severity":{"type":"string","enum":["none","low","medium","high","critical"]},
   "findings":{"type":"array","items":{"type":"object","additionalProperties":false,
     "properties":{
       "severity":{"type":"string","enum":["low","medium","high","critical"]},
       "title":{"type":"string"},
       "location":{"type":"string"},
       "recommendation":{"type":"string"}},
     "required":["severity","title"]}}},
 "required":["max_severity","findings"]}
JSON
}

# review_prompt <range> : the prompt sent to the review. Overridable via
# $SECURITY_REVIEW_PROMPT (the literal string "{RANGE}" is substituted).
review_prompt() {
  local range="$1"
  if [ -n "${SECURITY_REVIEW_PROMPT:-}" ]; then
    printf '%s' "${SECURITY_REVIEW_PROMPT//\{RANGE\}/$range}"
    return
  fi
  printf '/security-review\n\nReview ONLY the changes introduced by the git commit range %s (inspect with `git diff %s` and `git log %s`). Identify security vulnerabilities. Set max_severity to the highest severity found, or "none" if there are no security issues. Respond strictly per the provided JSON schema.' \
    "$range" "$range" "$range"
}

# review_run <range> : run the headless review. Prints raw CLI stdout; returns
# the CLI exit code. Read-only tool allowlist, cost-capped, non-interactive.
review_run() {
  local range="$1"
  "${CLAUDE_BIN:-claude}" -p "$(review_prompt "$range")" \
    --output-format json \
    --json-schema "$(review_schema)" \
    --allowedTools "${SECURITY_REVIEW_ALLOWED_TOOLS:-Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(git show:*) Bash(git status:*) Bash(git rev-parse:*) Bash(git branch:*)}" \
    --model "${SECURITY_REVIEW_MODEL:-sonnet}" \
    --max-budget-usd "${SECURITY_REVIEW_MAX_USD:-1.00}"
}

# review_extract_verdict <claude_stdout> : print the validated verdict JSON on
# stdout; return 0 on success, nonzero if the envelope is an error or the
# verdict cannot be recovered (so the caller fails closed).
review_extract_verdict() {
  local raw="$1" subtype iserr verdict
  subtype="$(printf '%s' "$raw" | jq -r '.subtype // empty' 2>/dev/null)" || return 1
  [ "$subtype" = "success" ] || return 1
  iserr="$(printf '%s' "$raw" | jq -r '.is_error // empty' 2>/dev/null)"
  [ "$iserr" = "true" ] && return 1

  # Prefer the schema-validated structured_output; fall back to parsing the
  # .result string (also JSON) for CLI builds that omit structured_output.
  verdict="$(printf '%s' "$raw" | jq -c '.structured_output // empty' 2>/dev/null)"
  if [ -z "$verdict" ] || [ "$verdict" = "null" ]; then
    verdict="$(printf '%s' "$raw" | jq -r '.result // empty' 2>/dev/null | jq -c . 2>/dev/null)" || return 1
  fi
  [ -n "$verdict" ] || return 1
  printf '%s' "$verdict" | jq -e 'has("max_severity")' >/dev/null 2>&1 || return 1
  printf '%s' "$verdict"
}

# review_max_severity <verdict_json> : print .max_severity.
review_max_severity() {
  printf '%s' "$1" | jq -r '.max_severity // empty' 2>/dev/null
}
