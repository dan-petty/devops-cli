# Design

## Decisions

- **Use `pydantic_ai`'s `first_event_timeout` instead of a custom `WrapperModel` deadline**: `pydantic_ai v2.73.0` enforces `ModelSettings["first_event_timeout"]` inside `RequestDeadline` and `FallbackModel.request_stream` per send and automatically closes the timed-out stream via `stream_under_deadline`. Role-only SSE chunks and `: ping` comments emit no stream event, so the deadline stops only on the first real content/tool event.
- **Keep `first_event_timeout` per-send while keeping `request_timeout` over all sends**: Override `GatewayCallModel._start_request_deadline` to pass `stream=False` so the outer deadline tracks `request_timeout` over the entire call without cutting retries at one `first_event_timeout` window, while `self._streams` (`FallbackModel`) starts a fresh `first_event_timeout` on each attempt.
- **Retry only `first_event_timeout` in `failed_before_first_event`**: Match `isinstance(error, ModelRequestTimeout) and error.setting == "first_event_timeout"` so whole-call `request_timeout` failures still stop immediately without retrying.
- **Report `timed_out=True` in `model_call_error`**: Include `ModelRequestTimeout` alongside `ModelTimeoutError` in `src/devops_cli/roadmap/agent_run.py` so exhausted `first_event_timeout` or `request_timeout` errors report `timed_out=True`.
- **Validate nesting on `AIConfig`**: Require `first_token_timeout_seconds < request_timeout_seconds` with a `model_validator(mode="after")` naming both `ai.first_token_timeout_seconds` and `ai.request_timeout_seconds`.

## Rejected alternatives

- **Custom `FirstTokenDeadlineModel(WrapperModel)` and `FirstTokenTimeout` class**: Rejected per `AGENTS.md` Rule 3 because `pydantic_ai` now provides native `first_event_timeout` enforcement and `ModelRequestTimeout.setting`.
- **Retry every `ModelRequestTimeout`**: Rejected because an exhausted `request_timeout` means the whole-call budget is spent and must not resend.
- **Validator comparing `ai.first_token_timeout_seconds` against the K8s gateway router timeout**: Rejected because the gateway router timeout lives in `k8s/llm/gateway/config.yaml`, not in runtime `Settings`.
