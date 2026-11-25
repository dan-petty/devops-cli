# Proposal: #6000

## Why

LiteLLM stream keep-alive comments (`: ping\n\n` every 30 s) reset per-read socket timeouts before any content token arrives, so a call to a stalled upstream deployment waits up to the whole-call deadline instead of timing out early and retrying once.

## What Changes

- Add `DEFAULT_AI_FIRST_TOKEN_TIMEOUT_SECONDS = 60` in `src/devops_cli/config/defaults.py` and `ai.first_token_timeout_seconds` (`int`, `ge=1`, default `60`) in `AIConfig` (`src/devops_cli/config/settings.py`), with a model validator refusing `first_token_timeout_seconds >= request_timeout_seconds` and error naming both settings.
- Use `pydantic_ai`'s built-in `ModelSettings["first_event_timeout"]` inside `GatewayCallModel` (`src/devops_cli/ai/models/gateway.py`) and pass `first_token_timeout=ai_cfg.first_token_timeout_seconds` from `_gateway_call_model` (`src/devops_cli/ai/pydantic_ai_bridge.py`).
- Override `_start_request_deadline` on `GatewayCallModel` with `stream=False` so outer call deadlines enforce `request_timeout` across all sends while each send inside `FallbackModel` gets its own `first_event_timeout`.
- Allow `failed_before_first_event` to retry `ModelRequestTimeout` when `error.setting == "first_event_timeout"`, and make `model_call_error` (`src/devops_cli/roadmap/agent_run.py`) set `timed_out=True` for `ModelRequestTimeout`.
- Add unit tests in `tests/ai/models/test_gateway_call.py` and `tests/ai/client/test_roadmap_agent_run.py`, and regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`.

## Capabilities

### Modified Capabilities

- `ai-agent-stream-retry`: Enforce `ai.first_token_timeout_seconds` via `pydantic_ai`'s `first_event_timeout`, retry `first_event_timeout` closures up to `ai.max_retries` times, and validate `ai.first_token_timeout_seconds < ai.request_timeout_seconds`.

## Impact

- Stalled streams with SSE keep-alive comments end after `ai.first_token_timeout_seconds` and resend cleanly, while post-first-token pauses remain governed only by `ai.request_timeout_seconds`.
- Gateway router timeout (`900 s`) and `ai.request_timeout_seconds` (`1200 s`) stay above the default `60 s` first-token deadline.

## Feasibility

Verified directly against `origin/main` (`feddcc2d8`) and installed `pydantic-ai v2.73.0`:
- `ModelSettings` supports `first_event_timeout`, `StreamedResponse` and `FallbackModel.request_stream` enforce it per send while closing timed-out streams, and keep-alive comments or role-only chunks still trigger `ModelRequestTimeout(..., setting="first_event_timeout")`.
- `GatewayCallModel` currently sets only `request_timeout` and `max_retries` in `self._defaults`, and `failed_before_first_event` does not retry `ModelRequestTimeout(setting="first_event_timeout")`.

## Existing Tool Considered

The installed in-use library `pydantic-ai` (`v2.73.0`) provides native `ModelSettings["first_event_timeout"]` and `ModelRequestTimeout(setting="first_event_timeout")` per stream send, which did not exist at the 2026-11-17 alternatives check. Instead of building a duplicate custom `WrapperModel` deadline loop and custom timeout exception, this change wires `pydantic-ai`'s native `first_event_timeout` into `GatewayCallModel`, `failed_before_first_event`, `AIConfig`, and `model_call_error`.
