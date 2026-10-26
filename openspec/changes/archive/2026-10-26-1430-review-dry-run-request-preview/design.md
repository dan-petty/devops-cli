# Design: Review Dry Run Model Request Preview

## Context

In review dry runs, inspecting the request the model client would send requires parity with real calls. Hand-crafted request constructors inevitably drift as provider implementations evolve (such as Anthropic Messages API, OpenAI SDK migrations, adaptive thinking, and sampling configurations). By capturing requests via `httpx2.MockTransport`, the actual SDK or provider mixin builds the request payload.

## Architecture

1. **Client Factory Transport Injection**:
   - `LLMClient` accepts an optional `transport: httpx2.BaseTransport | None` or `http_client: httpx2.Client | None`.
   - When provided, `_create_http_client` and `_shared_client` use the provided transport or client instead of creating new pooled connections.
   - `get_llm_client` in `src/devops_cli/ai/client/factory.py` forwards `transport` and `http_client` to `LLMClient`.

2. **Recording Preview Handler (`_llm_request_preview`)**:
   - Constructs a recording `httpx2.MockTransport` that intercepts outbound HTTP requests, buffers the request content, and responds with synthetic valid minimal responses (e.g. 200 OK message/completion structure) so client execution completes cleanly.
   - Executes `client.chat(system, user, **kwargs)` with the recording transport installed.
   - Extracts the recorded request, masks sensitive headers (`Authorization`, `x-api-key`) with `mask_secrets`, and returns an `LLMRequestPreview` object that supports dict access (`method`, `endpoint`, `url`, `headers`, `json`, `body`), attribute access, and equality comparison against `httpx2.Request`.

3. **Subprocess Dry-Run and Bus Isolation**:
   - In `src/devops_cli/core/process.py`, `_apply_github_token` checks `is_dry_run()` and skips token resolution when active.
   - `DEFAULT_ALLOWED_ENV_VARS` includes `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` so subprocesses honor test-floor bus isolation fixtures.

## Alternatives Rejected

1. **Maintaining Provider-Specific Serializers in Runner**:
   - *Rejected*: Re-implementing provider-specific serializer branches in `_llm_request_preview` proved fragile, drifting immediately when Anthropic or OpenAI SDKs updated. Evidence: audit findings in #1430 where `claude`, `gateway`, `openai`, and `ollama` endpoints and payloads diverged from runtime behavior.

2. **Intercepting via Pydantic Model Dumps without HTTP Mocking**:
   - *Rejected*: Pydantic models alone do not capture headers, wire URLs, query parameters, or SDK-specific wrapper headers (such as `anthropic-version` or trace context headers).
