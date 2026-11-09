# Proposal: #4220

## Why

A stage plan run on `claude-sonnet-5-5` ends with `StructuredOutputValidationError: 0 schema violation(s)` (#4220). The request sets no `max_tokens`, so the gateway sends the Anthropic default of 4096 output tokens. The final reply of a plan is longer than that. The provider cuts it with `finish_reason` `length`, and the cut reply holds no part. pydantic-ai raises `UnexpectedModelBehavior` ("Model token limit (provider default) exceeded before any response was generated"). The stage code reads a run whose last reply has no function tool call as a broken schema, and prints only the count of violations, which is 0. The message of the real cause is lost. A trial of Sonnet on the stage task cost about 18 USD per hour in rounds that all failed here.

## What Changes

- `_claude_group_model` in `src/devops_cli/ai/pydantic_ai_bridge.py` builds the model with `settings=ModelSettings(max_tokens=CONST_AI_CLAUDE_GROUP_MAX_OUTPUT_TOKENS)`. The constant is 32,000 in `src/devops_cli/config/constants.py`. Another model keeps the limit of its gateway entry. The cap is in the client only, and not in `k8s/llm/gateway/config.yaml`.
- `InvestigationStopped` gets the field `output_limit`. `investigate` sets it when the run ends with `UnexpectedModelBehavior` and the last model reply has `finish_reason` `length`. Such a stop is not a broken schema, so `schema_broken` is false for it.
- `ToolboxClient` raises `RoadmapStageError` with a new message of `MESSAGES.roadmap` for a stop with `output_limit`, for the plan run and for the review run. The message names the output token limit and `max_tokens`, so `_failure_of` in `stage.py` shows it as the reason of the failure, and no longer shows a count of violations.
- The change adds two requirements, because the request that a Claude group gets and the reason of a failed item are observable: one in `ai-gateway-routing`, one in `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: adds the requirement `A request to a Claude group carries an output cap`.
- `roadmap-stage`: adds the requirement `A reply cut by the output token limit names the limit`.

## Impact

- Code: `src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`.
- Tests: `tests/ai/test_pydantic_ai_profiles_and_providers.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/support/length_stop.py`.
- No new setting: the cap is a constant, so no ConfigMap changes and no rollout order.
- A Claude group with a longer reply now uses more output tokens at most; the cap is a ceiling, and a shorter reply costs the same.

## Feasibility

- Library: pydantic-ai 2.59.0 is installed. `OpenAIChatModel.__init__` takes `settings`, and a check in the venv printed `True` for `"settings" in inspect.signature(OpenAIChatModel.__init__).parameters`. The implement step (#2869) already sends `max_tokens` this way, and the fake gateway of `tests/roadmap/implement/test_roadmap_implement_step_output_cap.py` reads it on the wire as `max_completion_tokens`.
- Cause: `pydantic_ai/_agent_graph.py` raises `UnexpectedModelBehavior("Model token limit (<max_tokens or provider default>) exceeded before any response was generated ...")` for a reply with no part and `finish_reason` `length`. A test that serves such a reply from a fake gateway through the real `OpenAIChatModel` reproduces the run of item #3599: on origin/main the stage error reads "The plan run stopped before it gave a plan: Model token limit (provider default) exceeded ...", it is a `StructuredOutputValidationError`, and `_failure_of` in `stage.py` prints "0 schema violation(s)".
- Limit: `claude-sonnet-5-5` has a 1M-token context and 128,000 output tokens (claude-api reference). A cap of 32,000 is about 8 times the default of 4096, holds a `StageProposal` (the body alone may take 8,192 tokens) and the thinking tokens, and is far under the model limit.
- Not verified here: whether LiteLLM applies `litellm_params.max_tokens` of a gateway entry as a default when a request sets none. LiteLLM is not installed in the venv. The change does not need it, because the client sends the cap. The Publish stage may check it with one tiny live call.
- First check, which fails on origin/main: `uv run devops ci fail-to-pass --base origin/main`. Second check: `uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py`. Third check: one live stage plan of a small item through the gateway ends with no length stop.

## Existing Tool Considered

pydantic-ai `ModelSettings(max_tokens=...)` on `OpenAIChatModel(settings=...)` covers the cause with one argument; it is the same tool that #2869 uses for the implement step. The stop is read from `ModelResponse.finish_reason`, which the library reports, so no text of a message is parsed. The change builds nothing new and deletes no internal code.
