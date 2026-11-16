# Proposal: #5965

## Why
A model call to the LLM gateway is retried in layers that do not agree, and the failure that hurt most is retried by none of them (#5965). From 10:40Z to 11:35Z on 2026-11-16, OpenRouter wrote a timeout error into 12 open streams. The gateway and the client had a status 200 already, so no retry and no fallback ran, and 12 roadmap steps failed with the class `provider`.

The pydantic-ai path (refine, alternatives, stage, implement) does not read `ai.max_retries`. Its HTTP transport makes 3 attempts and the OpenAI SDK under it makes 3 more, so one call can go to the gateway 9 times, and the gateway retries each one 5 times and falls back. Only the implement step has a deadline for one call. The router timeout of 1500 s is above that deadline (1200 s), so the client ends a stuck call before the gateway can retry it or fall back.

## What Changes
- The gateway owns the retries and the fallbacks of a call. A pydantic-ai call to a gateway chat group goes through `GatewayCallModel`, which sends the call at most `ai.max_retries` + 1 times. It sends a call again only when the call did not reach the gateway (a connect or pool failure), or when a streamed reply failed before its first event. A status that the gateway answers is not sent again. A failure after the first event fails the call once.
- The OpenAI SDK makes no retry of a gateway call (`ModelSettings.max_retries` 0), and the HTTP client of a gateway chat group has no retry transport.
- The direct client (`LLMClient` with provider `gateway`) sends a call again only after a failed connect, `ai.max_retries` + 1 times. The other providers keep their retries.
- New setting `ai.request_timeout_seconds` (default 1200): one deadline over all sends of a pydantic-ai gateway call and the read of its stream (`ModelSettings.request_timeout`). The implement step keeps its own setting, which the settings refuse above `step_time_limit_seconds`.
- The router timeout of the gateway goes from 1500 s to 900 s, below the default call deadline, so the gateway ends a stuck attempt first and can retry or fall back.
- The unused `StreamRetryModel` of the bridge and its tests are deleted.

Each item changes behavior that a caller sees, so the change has spec deltas. It fits one pull request.

## Capabilities
- Modified: `ai-agent-stream-retry` (the resend rules, the count, the transport, the deadline).
- Modified: `ai-gateway-routing` (the router timeout nests inside the call deadline; the direct client resends only a failed connect).
- Modified: `roadmap-implement-step/model-calls` (the requirement of the step deadline is replaced: the router timeout is below the deadline of a step call, and the deadline is not above the step limit).

## Impact
- In the cluster (`ai.max_retries: 1`) a call goes to the gateway at most two times. Before, the pydantic-ai path sent it up to 9 times.
- A stream that the provider fails before its first event is sent again once, as in the outage of 2026-11-16.
- Refine, alternatives and stage calls end after 1200 s at most. Before, keepalive pings could hold them open until the Job deadline.
- A gateway change reaches the cluster through Argo CD after the merge.
- The new check of `roadmap.implement.request_timeout_seconds` against `step_time_limit_seconds` tightens a setting that the ConfigMap names. The live ConfigMap `devops-cli-config` holds 2400 and 10800 (read on 2026-11-16), and the template holds the same, so the check accepts both and the live ConfigMap needs no change first. The new setting `ai.request_timeout_seconds` has a default, and no ConfigMap names it.

## Feasibility
- LiteLLM 1.103.11 (the pinned image), `litellm_core_utils/streaming_handler.py`, `_handle_stream_fallback_error`: an error in a stream with a 4xx status other than 429 is raised directly, with no `MidStreamFallbackError`, so the router does no fallback. `llms/openrouter/chat/transformation.py` `chunk_parser` raises the `error` object of a chunk as `OpenRouterException`, and `exception_mapping_utils._map_openrouter_exception` maps code 408 to `litellm.Timeout`, whose status is 408. The router retries wrap `_acompletion` only, which returns before the stream is read.
- Loki, gateway pod, 2026-11-16T11:35:48Z: `litellm.Timeout: Timeout Error: OpenrouterException - Message: A Timeout Occurred, Metadata: {'error_type': 'timeout'}` in `proxy_server.async_data_generator()`, which is after the status 200.
- LiteLLM has no first-chunk timeout and no setting to fall back on an in-stream 408 (`router.py`, `types/router.py` `RetryPolicy`). LiteLLM 1.109.1, the latest release, exempts only a transport read timeout (`_is_transport_timeout`), not the 408 of an OpenRouter error chunk.
- `proxy/common_request_processing.py`: with `sse_keepalive_ping_interval_seconds: 30`, the proxy sends the status 200 before the first chunk, and a later failure reaches the client as an SSE error frame.
- pydantic-ai 2.59.0: `FallbackModel.request_stream` waits for the first event of a stream and sends the request to its next model when the stream fails before it. `ModelSettings.request_timeout` is one deadline over every attempt and the read of the stream. `ModelSettings.max_retries` sets the SDK retries. openai 3.49.0 has `DEFAULT_MAX_RETRIES` 2.

## Existing Tool Considered
- pydantic-ai `FallbackModel`, used: it holds the same gateway model `ai.max_retries` + 1 times, with a `fallback_on` rule that accepts only a failure before the first event. It waits for the first event, so a role-only first chunk of LiteLLM does not end the resend window.
- pydantic-ai `ModelSettings.request_timeout` and `max_retries`, used: one deadline per call, and no SDK retries.
- LiteLLM router settings, kept as the owner of the retries and the fallbacks. No LiteLLM setting covers the in-stream 408 (see Feasibility).
- Internal code deleted: `StreamRetryModel`, `_StreamRetryProxy`, `wrap_stream_retry_model`, `_is_retryable_error`, `_backoff_sleep` and `_to_ai_client_error` in `src/devops_cli/ai/pydantic_ai_bridge.py`, and their tests.
