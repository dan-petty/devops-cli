# Proposal: #5532

## Why
A short outage of a cluster service ends a devops command with a Python traceback, and the command does not try again (#5532). On 2026-11-13, `devops prometheus query` got `503 Service Unavailable` 12 s after the Prometheus pod started again after a planned node drain. The command printed `httpx2.HTTPStatusError` and a traceback of 70 lines. One more attempt some seconds later would have passed. The health gate of `devops infra apply` reads Prometheus soon after each drain, which is when Prometheus can be restarting.

#5487 is the 4xx branch of the same failure: a query that Prometheus refuses with HTTP 400 also ends in a traceback, and the error text of Prometheus is lost.

## What Changes
- The `retries` option of `devops_cli.http.entry.http_client` also takes a `ReadRetryPolicy` (`devops_cli.http.retry`). With a policy, the client sends a GET, HEAD or OPTIONS request again after 429, 502, 503 or 504, and after a failed connect or read. The waits back off exponentially with jitter, and they obey `Retry-After`. The policy `SERVICE_READ_RETRY` makes at most 4 attempts, and it starts no attempt after 20 s, which is less than the shortest command timeout (`DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS`, 30 s). It never sends again a request with another method, a request that got another status, or a request that the egress check refused (`SSRFBlockedError`). When the attempts or the time end, the client gives the last answer, or raises the last network error, as one attempt does. The integer form of `retries` (the AI clients) does not change.
- A pooled client keys on its retry option too, so a client that retries and one that does not never share a pool entry.
- One function, `service_error`, maps the last failure of a request to a cluster service to one `DevOpsCLIError` subclass, `ServiceRequestError`. Its message is one line: the service, the HTTP status or the network error, the number of attempts, the time, and a hint. When the reply holds an error text, it adds the `error` field (with `errorType`) or the `message` field of a JSON body, or the first line of a plain text body, so a refused PromQL query shows the parse error of Prometheus (#5487). The exit status is 1. The command prints no traceback.
- These clients use the policy and the mapping: `PrometheusClient` (`devops prometheus`, the rollout metric gate and the health gate of `devops infra apply`), the Loki metric queries of `devops roadmap eval grades` (`query_loki_metrics`), `GrafanaClient` (its reads; its POST requests are sent once), and `get_json` of `k8s/service_http.py`.
- These calls keep their contract, and send each request one time: `reaches_service` (one GET tells whether the API server reaches a Service), the poll of the forward in `service_probe.forward_service` (its own wait loop retries), and the telemetry panel of the dashboard (it falls back at once to the data of the process).
- The health gate keeps its own wait loop. A Prometheus that stays down is a problem of the gate, with the mapped line as its detail.

This changes messages and behavior that a consumer sees, so the change has a spec delta.

## Capabilities
- `cluster-service-read-retry` (new): the retry policy of the reads of a cluster service, the clients that use it, the calls that keep their contract, and the one error line.
- `infra-apply`: the changed requirement "The cluster is healthy before the apply" gets a scenario for a Prometheus that stays down.
- `roadmap-job-grades`: the changed requirement "eval grades reads the result lines with metric instant queries" names `ServiceRequestError` for a query that Loki refuses.

## Impact
- Users of `devops prometheus`, `devops grafana`, `devops roadmap eval grades`, `devops infra apply` and `devops k8s service-url --fetch`: a restart of a service for some seconds no longer ends the command. A service that stays down ends the command with one line in place of a traceback, after at most about 20 s of attempts.
- `KubernetesLoggingError` is no longer raised by `query_loki_metrics` for a failed request; `ServiceRequestError` takes its place. `execute_loki_query` and its fallback to `kubectl logs` do not change.
- No setting, dependency or manifest changes. A release is necessary, because the fix is in the CLI.
- The change fits one pull request.

## Feasibility
- Source at `origin/main` (6eae49808): `http_client` in `src/devops_cli/http/entry.py` has a `retries` option. Of 49 call sites of `http_client` in `src/`, only `ai/client/base.py` passes it (`grep -rn "http_client(" src/`).
- `PrometheusClient._get_json` (`src/devops_cli/prometheus/client.py`) calls `response.raise_for_status()` with no retry, and `devops prometheus query` does not catch `httpx2.HTTPStatusError`. `_report_devops_error` in `src/devops_cli/core/cli.py` reports only a `DevOpsCLIError`, so the error propagates with a traceback. The new command test reproduces it on the base.
- `GrafanaClient._send`, `get_json` and `query_loki_metrics` send each request one time. `critical_alerts` in `src/devops_cli/infra/nodes.py` and `_fetch_metric_value` in `src/devops_cli/argo/rollouts.py` catch `httpx2.HTTPError` from the Prometheus client.
- The `retries` option as it is does not fit a read of a cluster service. `create_retry_transport` in `src/devops_cli/ai/retries/__init__.py` raises `httpx2.HTTPStatusError` for every 4xx and 5xx at the transport, and closes the reply, so a caller cannot read the body of a 400 (#5487) or treat a status itself. It sends again 408, 500 and every other 5xx, and any method, a POST too. Its wait (`wait_exponential`) has no jitter and no total time bound. Its wrapper records failed attempts in the AI spend ledger.
- `python -c "import pydantic_ai.retries"` with tenacity 9.1.4 takes 0.55 s and loads 850 modules more. The modules of `devops prometheus`, `devops grafana`, `k8s/logql.py`, `k8s/service_http.py` and `infra/nodes.py` already load `tenacity` but not `pydantic_ai`.
- `tenacity.Retrying` takes `stop`, `wait`, `retry`, `before_sleep`, `retry_error_callback` and `sleep`, and `wait_exponential_jitter` gives the jitter (tenacity 9.1.4 source). Tenacity reads `time.monotonic` itself, so the time bound reads the clock seam (`devops_cli.core.clock`), which the `clock` fixture fakes.
- #5487 is small in this change: the mapping reads the `error` and `errorType` fields of the JSON body that the Prometheus HTTP API documents for an error reply. So this change includes it.

## Existing Tool Considered
tenacity (Apache-2.0, already a dependency) gives the retry loop, the stop, the wait with jitter and the sleep seam. The pydantic-ai transport `HTTPX2TenacityTransport`, which the `retries` option uses for an integer, was rejected for these clients: it adds 0.55 s of imports to each command, and it closes the reply of a failed status. The change builds one thin transport over `tenacity.Retrying` (about 60 lines). Cost to build: about 0.3 M tokens and 2 hours. `parse_retry_after` of `devops_cli.github.error_classifier` reads `Retry-After`. The change deletes the network and status branches of `query_loki_metrics` and the `httpx2.HTTPError` catch of the health gate and of the rollout metric read, which the mapping replaces.
