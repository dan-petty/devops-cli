# Design

## Decisions

### One owner: the gateway
| Layer | Sends of one call after the change |
| --- | --- |
| Gateway router | `num_retries: 5` on the group, then the fallbacks (unchanged) |
| pydantic-ai client (`GatewayCallModel`) | at most `ai.max_retries` + 1; a second send only after a connect or pool failure, or a stream that failed before its first event |
| OpenAI SDK under pydantic-ai | 1 (`ModelSettings.max_retries` 0) |
| HTTP transport of a gateway chat group | 1 (no retry transport) |
| Direct client (`LLMClient`, provider `gateway`) | at most `ai.max_retries` + 1; a second send only after a connect or pool failure |

`GatewayCallModel` is a `WrapperModel` around the chat model of a gateway group. Its `request` goes through a `FallbackModel` that holds the chat model `ai.max_retries` + 1 times and falls back only on a failure that never sent the request (`ModelConnectionError` with the phase `connect` or `pool`). Its `request_stream` goes through a second `FallbackModel` that also falls back on a failure before the first event: an error frame inside the 200 stream (`ModelAPIError.in_stream`), a stream that broke (`ModelConnectionError` that is no timeout), or a stream that ended with no content (`UnexpectedModelBehavior`). A status that the gateway answers (`ModelHTTPError` that is not `in_stream`) and the deadline (`ModelRequestTimeout`) are not sent again. When each send fails, the model raises the last error, not the `FallbackExceptionGroup`, so a caller that catches `ModelAPIError` keeps its class. A `FallbackModel` does not wait between sends. The gateway Deployment rolls its pods one by one, so a failed connect seldom repeats, and the gateway waits between its own retries.

An error frame before the first event can also be the late error of the gateway after its own retries, when its keepalive sent the status 200 first. The client cannot tell the two apart, so it sends the call again. `ai.max_retries` bounds that resend: in the cluster, a call goes to the gateway at most two times.

The system-one provider of TypeSafe Jev goes through a pass-through route that the gateway does not retry, so it keeps its transport retries.

### One deadline per call
`GatewayCallModel` adds `request_timeout` from `ai.request_timeout_seconds` to its settings. A `WrapperModel` gives the deadline of its inner model to the agent graph, so the graph starts one deadline over the open of the stream, every send of the `FallbackModel` and each read. The `FallbackModel` starts a deadline for each send too, but each one starts later than the one of the graph, so the deadline of the graph ends first. The implement step sets `request_timeout` in its agent settings from `roadmap.implement.request_timeout_seconds`, which overrides the default.

The timeouts nest, and the inner one ends first:

| Timeout | Default | Cluster |
| --- | --- | --- |
| `terminationGracePeriodSeconds` of the gateway pod | 600 s | 600 s |
| Router `timeout` (a non-streamed reply, or the wait for the next chunk) | 900 s | 900 s |
| `devops-background` deployment `timeout` | 1100 s | 1100 s |
| `ai.request_timeout_seconds` | 1200 s | 1200 s |
| `roadmap.implement.request_timeout_seconds` | 1200 s | 2400 s |
| Stage Job margin (`CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS`) | 1800 s | 1800 s |
| `roadmap.implement.step_time_limit_seconds` | 5400 s | 10800 s |
| Runner Job deadline (`cronjob-runner.yaml`) | 7200 s | 7200 s |

The settings refuse `roadmap.implement.request_timeout_seconds` above `step_time_limit_seconds`. The gateway sets `cancel_on_disconnect: true`, so the deadline of the client also frees the slot of a local tier, as before.

### A failure after the first event
The failure ends the call once. pydantic-ai raises `ModelHTTPError` with `in_stream` set for an error frame, or `ModelConnectionError` with the phase `read` for a cut stream, and the roadmap jobs classify it as before (`provider`).

## Rejected alternatives
- A LiteLLM setting or a LiteLLM upgrade: no setting falls back on an in-stream 408, and 1.109.1 exempts only a transport read timeout (proposal, Feasibility).
- `keepalive_seconds: 0` on the hosted groups: the 408 then reaches the client as an HTTP status, but the router still does no fallback on it (the same 4xx rule), and the Cloudflare edge cuts a call with no data for 125 s (#2365).
- An own `WrapperModel` loop that resends when the stream fails on open: the OpenAI model reads only the first chunk on open, and LiteLLM sends a role-only first chunk (`CustomStreamWrapper.strip_role_from_delta`). A failure after that chunk and before the first token would not be sent again. Reading the first event needs the private `_event_iterator` of the stream, which `FallbackModel` already sets.
- A `FallbackModel` alone: it starts a new deadline for each send (pydantic-ai `models/_request_timeout.py`), so two sends could take twice the deadline.
- A retry in the HTTP transport: it returns at the response headers, so it cannot see a stream that fails after the status 200.
- Keep the SDK retries: the OpenAI SDK retries 408, 409, 429 and 5xx, which the gateway retried already.
