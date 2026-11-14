# Proposal: #3578

## Why

Some gateway requests reach the proxy with no caller name, so `litellm_proxy_total_requests_metric_total` counts them as `end_user="None"`. Every client of this repository sends `x-litellm-end-user-id`, but `gateway_caller_headers` takes its value from `otel_service_name()`, which returns an empty string when a process sets `OTEL_SERVICE_NAME=""`. LiteLLM cannot name a caller that sends no value, so the client must always send one. Closes #3578.

## What Changes

- `gateway_caller_headers` sends `devops-cli` as the end-user value when the process's OTel service name is empty.
- The header test runs the chat, embedding and pydantic-ai paths with an empty `OTEL_SERVICE_NAME`, so each recorded request holds a non-empty value.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gateway-caller-telemetry`: An empty service name still names devops-cli.

## Impact

- Code: `src/devops_cli/ai/client/network.py`
- Tests: `tests/ai/client/test_gateway_caller_headers.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The header comes from the OTel name: `src/devops_cli/ai/client/network.py:71:return {"User-Agent": user_agent(), _GATEWAY_END_USER_HEADER: otel_service_name()}`.
- The name has no empty fallback: `src/devops_cli/telemetry/tracer.py:1520:return os.getenv("OTEL_SERVICE_NAME", CONST_OTEL_SERVICE_NAME)`.
- The default is `devops-cli`: `src/devops_cli/config/constants.py:2044:CONST_OTEL_SERVICE_NAME = "devops-cli"`.
- The three paths share the header: `tests/ai/client/test_gateway_caller_headers.py` already checks the chat, embedding and agent calls with a named and a default service.
- The new case passes on the branch: `uv run devops ci test tests/ai/client/test_gateway_caller_headers.py`.

## Existing Tool Considered

LiteLLM (`BerriAI/litellm`) is the open, maintained proxy that reads the header into the `end_user` label, and it accepts no request with no caller name. The client must send a value, so the change is a fallback of one expression and a test parameter.
