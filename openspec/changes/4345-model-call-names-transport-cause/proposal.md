# Proposal: #4345

## Why

On 2026-11-10, five parallel runs of `devops roadmap eval verify --model deepseek-v4.1-flash-1017` lost 6 of 48 cases to `AIClientError: The investigation's model call failed (ModelConnectionError).` The message names only the class of the pydantic-ai error. `model_call_error` drops the phase of the transport and the error of the HTTP library, so the stored reports cannot tell a dropped stream from a refused connection or a failed name lookup. Closes #4345.

## What Changes

- `model_call_error` adds, for a `ModelConnectionError` or a `ModelTimeoutError`, the phase of the transport (`ModelConnectionError.phase`: `pool`, `connect`, `write` or `read`) and the class and the text of the first error of the cause chain. pydantic-ai keeps the error of the OpenAI SDK as `__cause__`, and the SDK keeps the error of `httpx2` as its own, so the first error is the error of the HTTP library. `bounded_text` masks and cuts the text, as for other stop text.
- The message of a failed call with no cause, and of every other failed call, does not change.
- The change adds no retry. The OpenAI SDK keeps its default of two retries for a request that gets no response.

The message is output of the investigation and of the implement step, so the change carries a spec delta in `ai-client-error-reason`.

## Capabilities

- `ai-client-error-reason`: one ADDED requirement (a failed transport names its phase and its error).

## Impact

- `src/devops_cli/roadmap/agent_run.py`: `model_call_error` and `_transport_cause`.
- `tests/roadmap/refine/test_roadmap_refine_investigation.py`: the message of a failed transport, through the investigation.
- Every caller of `model_call_error` (the investigation of refine, stage and the verify eval, and the implement step) shows the new detail. The stored report of `devops roadmap eval verify` holds it in the `error` of a failed case.

The change fits one pull request.

## Feasibility

The issue names three possible causes. The logs of the time of the failures rule out all three, and point to the path between the client and the edge of the tunnel.

- **The times of the failures.** The client exported one trace for each of the five processes to Tempo. The `git` checkout spans in the worker thread of each case give the start of each case, and the order of the cases in each batch gives the failed case. The six failures ended at 03:30:56Z (case 2531), 03:30:56Z (case 2554), 03:35:48Z (case 2524), 03:35:54Z (case 2526), 03:41:44Z (case 2559) and 04:01:31Z (case good-3410). Two separate processes failed in the same second, and two more 6 s apart. Two cases failed 36 s and 17 s after they started; four failed after 1 to 8 minutes of their run.
- **Not a limit of the gateway.** The gateway (LiteLLM) logged `200 OK` for every `POST /v1/chat/completions` from 02:30Z to 04:40Z, and no other line (Loki, `service_name="llm-gateway"`, 32,426 lines). The agent runs stream each model request (`drain_events`), and the server writes the `200 OK` line when the response starts, so the line does not show that a stream ended. But the gateway logged no error and no restart.
- **Not the tunnel.** `cloudflared` kept 8 HA connections for the whole time (`cloudflared_tunnel_ha_connections`). Its error counter (`cloudflared_tunnel_request_errors`) went up once, at 03:38Z, when a stream of another request was canceled; that time is in no failure window. The tunnel logged no error at the six times. A client that drops an open stream makes the edge cancel the stream to `cloudflared`, which logs `stream ... canceled by remote`, as at 03:38Z.
- **Not a timeout.** pydantic-ai raises `ModelTimeoutError`, a subclass, for a timeout, and `model_call_error` writes the class name. All six messages name `ModelConnectionError`.
- **Not a stale connection of a closed event loop (#4319).** `Agent.run_sync` drives each run on the event loop of its thread (`pydantic_graph._utils.run_until_complete`). In each process, all `git` spans of the checkouts of the cases come from one AnyIO worker thread (for example thread `…493696`, from 02:46:40Z to 04:16:31Z), so all cases of a process ran on one event loop.
- **Not the cluster path.** The roadmap Service in the cluster calls the gateway by its Service name, not through the tunnel. In the 7 days to 2026-11-11 it logged no `ModelConnectionError`; each of its failed model calls had an HTTP status (500 or 502).
- **What is left.** No stream through the tunnel was canceled at the six times, and two processes failed at the same second. So the failed requests most likely had no open stream through the tunnel: the transport failed before the request reached the edge (name lookup, TCP or TLS on the client host), or the edge closed the client connection with no cancel of the stream to `cloudflared`. Both are on the path between the client host and the edge of the tunnel, outside the project. The logs cannot tell which. The OpenAI SDK (`AsyncOpenAI` from `pydantic_ai.providers._openai_compatible`, no `max_retries`, so the default of 2) retries a request that gets no response, so a failure that reaches the run broke a started response or lasted through three attempts. The class of the transport error is not in the reports, because `model_call_error` drops it.

The change makes the next failure name its phase and its transport error, so a person can tell a dropped stream from a refused connection. A retry would hide the cause, as the issue states, so the change adds none. `devops roadmap eval verify --resume` (#4344) runs again only the failed cases of a stored report.

## Existing Tool Considered

pydantic-ai already finds the phase of a transport error (`ModelConnectionError.phase`, from `pydantic_ai._model_errors.transport_phase`) and keeps the error of the SDK as `__cause__`. The change reads both and adds no library. The masking is the existing `bounded_text` of `devops_cli.security.sanitizer`. Written cost: about 15 000 tokens and 30 minutes to build, and no upkeep beyond the test. The change deletes no code.
