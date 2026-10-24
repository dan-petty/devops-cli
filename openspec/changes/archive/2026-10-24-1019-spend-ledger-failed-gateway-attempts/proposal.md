# Proposal

## Why

Issue #1019: the spend ledger counted fewer requests than the LLM gateway. Every `LLMClient` HTTP client wraps its transport in a tenacity retry transport (`create_retry_transport`), which retries 5xx, 408, 429, timeouts and transport errors up to `max_retries + 1` attempts. Previously, `_dispatch_messages` only recorded spend after the provider returned, so retried attempts inside the transport and attempts that ultimately failed wrote no ledger rows. Furthermore, while #2031 added `served_model` recording from `x-litellm-model-name` headers, when gateway headers omitted it but the reply JSON body contained the resolved model, the ledger only recorded the requested alias.

## What Changes

- A new `AttemptRecordingTransport` sits between egress and retry in `new_http_client`.
- When an attempt reaches the gateway and fails (HTTP status >= 400 or read timeout), `AttemptRecordingTransport` records one row in the spend ledger with finish reason `error`, wall-clock elapsed time, 0 tokens (unless the provider reported usage), and any serving backend or deployment model named in headers or error JSON.
- A connection failure (`ConnectError`, `ConnectTimeout`) opens no socket to the gateway and writes no row.
- Successful attempts continue to be recorded upon reply completion as today.
- When gateway response headers omit `x-litellm-model-name`, but the reply JSON body or stream frame names a resolved model distinct from the requested alias, the resolved model is stored in `served_model`.
- Streams follow the same rule: failed attempts that reach the gateway write `error` rows per attempt.
- `k8s/README.md` is updated to clarify that the HTTP transport is the single retry layer.
- `tests/llm_stream_fakes.py` adds `route_retrying_client` to route innermost transport requests to mock handlers while preserving retry and attempt-recording transports.
- The change alters spend-ledger recording and telemetry emission, adding requirements to `ai-spend-pricing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: adds requirements that each failed HTTP attempt reaching the gateway is recorded in the spend ledger, and that a successful reply takes the served model from the reply body when response headers omit it.

## Impact

- Code: `src/devops_cli/ai/spend/transport.py` (new), `src/devops_cli/http/client.py`, `src/devops_cli/ai/client/network.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/streaming.py`.
- Documents: `k8s/README.md`.
- Tests: `tests/llm_stream_fakes.py`, `tests/test_ai_spend_dispatch.py`.

## Feasibility

- `new_http_client` in `src/devops_cli/http/client.py:160-169` constructs the egress transport and wraps it with `create_retry_transport` when `retries` is specified. Placing `AttemptRecordingTransport` directly around `transport` before `create_retry_transport` ensures every attempt executed by Tenacity passes through `AttemptRecordingTransport`.
- In `pydantic_ai.retries.HTTPX2TenacityTransport`, each attempt calls `self.wrapped.handle_request(req)`. An HTTP status >= 400 returns from the wrapped transport before `validate_response` raises `HTTPStatusError`. `AttemptRecordingTransport` intercepts the response, records the attempt with finish reason `error`, and returns it so Tenacity can retry. For a read timeout, `AttemptRecordingTransport` catches `httpx2.ReadTimeout`, records the failed attempt, and re-raises for Tenacity retry.
- In `unified.py`, `_dispatch_messages` and `chat_messages_stream` wrap provider calls in `active_dispatch_context`, providing `provider`, `model`, `request_type`, `task_name`, `server`, and `backend_info` to `AttemptRecordingTransport`.
- `tests/test_ai_spend_dispatch.py` runs entirely offline with `MockTransport` and patched clock sleep, taking well under 1 second.

## Existing Tool Considered

- Tenacity retry transport (`HTTPX2TenacityTransport` in `pydantic_ai.retries`) is already devops-cli's standard HTTP retry layer. Rather than replacing Tenacity or implementing custom retry loops, `AttemptRecordingTransport` hooks directly into the existing transport pipeline as a standard `httpx2.BaseTransport`.
- LiteLLM gateway metrics (`litellm_proxy_total_requests_metric_total`). Rejected as the sole source of truth for workstation runs because interactive and review runs can execute offline or against isolated mock environments where Prometheus is absent.
- The change deletes obsolete documentation claiming retry loops in both dispatch and transport in `k8s/README.md`.
