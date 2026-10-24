# Design

## Context

Gateway request counts previously exceeded rows in the spend ledger because retried and failed HTTP attempts were not recorded. The HTTP transport retry layer (`create_retry_transport`) retried transient errors up to 5 times inside `http_client.post` / `http_client.stream`. `_dispatch_messages` only invoked `track_request_spend` after provider completion, leaving retried and failed attempts invisible in the spend ledger, review profile, and telemetry.

## Goals / Non-Goals

**Goals:**

- Every HTTP attempt reaching the gateway that fails (HTTP status >= 400 or read timeout) is recorded in the spend ledger with finish reason `error`.
- A connection failure (`ConnectError`, `ConnectTimeout`) where no connection opens records no row.
- Successful requests continue to be recorded once upon reply completion with their actual tokens and duration.
- When gateway response headers lack `x-litellm-model-name`, but the reply JSON body or stream frame names a resolved model distinct from the requested alias, that model is captured in `served_model`.
- Review profiles and telemetry (`AI_REQUESTS_TOTAL`) reflect all attempts.
- All unit tests run offline in under 1 second.

**Non-Goals:**

- Recording internal retries that occur solely inside LiteLLM behind a single client request (addressed separately by gateway-level metric correlation).
- Embedding requests attempt recording (scoped to the embedding-recording change).

## Decisions

- **Place `AttemptRecordingTransport` between egress and retry in `new_http_client`.** In `new_http_client`, when `retries` is specified, `AttemptRecordingTransport` wraps the egress transport and is passed as `wrapped` to `create_retry_transport`. This ensures every attempt that Tenacity executes passes through `AttemptRecordingTransport`. Rejected: placing the recorder outside Tenacity. If placed outside, it would only see the final result of all retries, reproducing the missing attempts gap.
- **Pass call metadata via `active_dispatch_context`.** `LLMClient` instances share underlying HTTP clients via `get_shared_client`. An HTTP client therefore cannot bind a single task, provider, or model. Context variables set in `_dispatch_messages` and `chat_messages_stream` communicate the active call metadata to `AttemptRecordingTransport`. When no dispatch context is active, `AttemptRecordingTransport` passes requests through untouched.
- **Record 0 tokens for failed attempts unless usage is reported.** If an error response includes token usage in its payload, those tokens are recorded. Otherwise, prompt and completion tokens are recorded as 0, preventing speculative token estimates from skewing cost calculations while capturing wall time and request frequency accurately.
- **Capture resolved model from response body when headers omit it.** When `extract_served_model(headers)` returns None, but `raw_json.get("model")` or stream frame `payload.get("model")` yields a model distinct from the requested alias (e.g. `gpt-oss:20b` for `devops-review`), `served_model` records the resolved model.

## Risks / Trade-offs

- [A failed attempt receives an unparseable error response] → `AttemptRecordingTransport` safely falls back to 0 tokens and no served model, recording finish reason `error`.
- [Tenacity retries exhaust and raise `HTTPStatusError`] → All failed attempts have been individually recorded in the ledger with finish reason `error`; the caller catches or propagates the exception as before.
