# Proposal: #4228

## Why

A stage plan run on `claude-sonnet-5-5` through the gateway can end with `StructuredOutputValidationError: 0 schema violation(s)` (#4228). The gateway log (container `litellm`, namespace `llm`) of the live run of item #4062 holds warnings of this form: "Failed to parse tool call arguments for tool search_code (chat completions). Error: Extra data". The model asked for several tool calls in one reply, and the arguments of those calls reached one JSON text that does not parse. The request tells Anthropic nothing about parallel tool calls, so Anthropic may make several calls in one reply. When a call has arguments that do not parse, the run stops, and its failure line shows a count of 0 schema violations. That line hides the cause.

## What Changes

- `_claude_group_model` in `src/devops_cli/ai/pydantic_ai_bridge.py` adds `parallel_tool_calls=False` to the `ModelSettings` of the model. The gateway maps it to `tool_choice.disable_parallel_tool_use` of Anthropic, so Anthropic makes one tool call at a time. Another model keeps the setting of its provider.
- `InvestigationStopped` gets the field `invalid_arguments`. `investigate` sets it when the run ends with `UnexpectedModelBehavior` and a tool call of the last model reply holds arguments that are not valid JSON. Such a stop is not a broken schema, so `schema_broken` is false for it.
- `ToolboxClient` raises `RoadmapStageError` with a new message of `MESSAGES.roadmap` for a stop with `invalid_arguments`, for the plan run and for the review run. The message names the tool call with invalid arguments, so `_failure_of` in `stage.py` shows it as the reason of the failure.
- The change adds two requirements, because the request that a Claude group gets and the reason of a failed item are observable: one in `ai-gateway-routing`, one in `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: adds the requirement `A request to a Claude group forbids parallel tool calls`.
- `roadmap-stage`: adds the requirement `A tool call with invalid arguments names the cause`.

## Impact

- Code: `src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`.
- Tests: `tests/ai/test_pydantic_ai_profiles_and_providers.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.
- No new setting, so no ConfigMap changes and no rollout order.
- A Claude group run makes one tool call per reply, so a run can need more requests than before. The budget of requests and tool calls is unchanged.
- The pinned LiteLLM image `v1.103.0` (`k8s/llm/gateway/deployment.yaml`) is not changed. A bump of an image is a change that only a person makes.

## Feasibility

- Library: pydantic-ai 2.59.0 `OpenAIChatModel` sends `parallel_tool_calls` from `model_settings` when the request has tools (`models/openai.py`). `ModelSettings` has the key `parallel_tool_calls` (`settings.py`), and `OpenAIChatModel` takes `settings=`.
- Gateway: LiteLLM 1.103.0 `AnthropicConfig._map_tool_choice` maps `parallel_tool_calls` to `tool_choice.disable_parallel_tool_use = not value`, and it adds a `tool_choice` of type `auto` when the request sets none. This was checked in the gateway pod and in a scratch install of the same version.
- Observed: 10 warnings "Failed to parse tool call arguments ... Extra data" in 48 hours of the gateway log, for the tools `search_code`, `glob` and `bash`. The `search_code` ones come from a `POST /v1/chat/completions` of the stage run. No fallback to another model was counted in the Prometheus metrics, and the gateway answered no status 400 for `claude-sonnet-5-5`.
- Not proved: an offline replay with LiteLLM 1.103.0 (an Anthropic stream with a text block and two `tool_use` blocks, through the stream wrapper and the chunk builder) keeps the two calls apart with valid JSON. So the join does not come from a clean Anthropic stream, and the exact step of the gateway that joins the arguments is open. The Publish stage checks the fix with one live stage plan: it must end with a plan or a named cause, and the log of those minutes must hold no "Failed to parse tool call arguments" warning. If the warning stays after the setting, the change stops with the log as evidence, and no splitter of joined arguments is written.
- LiteLLM releases: v1.105.0 "salvage concatenated JSON tool call arguments" repairs the parse of joined arguments and does not stop the join. No release note names a fix for parallel tool calls on `/chat/completions` to Anthropic. The latest release on PyPI is 1.108.3. A bump is for a person to decide; this change reports it and makes none.
- Failure line: `pydantic_ai` retries a tool call whose arguments do not parse (an output tool or a function tool) until the retries end, then raises `UnexpectedModelBehavior`. The last model reply of the run holds that call, so the arguments can be read from the messages with `pydantic_core.from_json`, and no text of an error is parsed.
- First check, which fails on origin/main: `uv run devops ci fail-to-pass --base origin/main`. Second check: `uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py`. Third check: the live stage plan above.

## Existing Tool Considered

The Anthropic setting `disable_parallel_tool_use`, which LiteLLM maps from the OpenAI field `parallel_tool_calls`, and pydantic-ai `ModelSettings(parallel_tool_calls=False)`. One added setting covers the cause at its source. The stop is read from the messages of the run, which the library keeps, with `pydantic_core.from_json`. The change builds nothing new and deletes no internal code.
