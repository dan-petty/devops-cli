# Design

## Decisions

### One policy behind the `retries` option
`http_client(level, retries=SERVICE_READ_RETRY)` puts `ReadRetryTransport` (`src/devops_cli/http/retry.py`) on the transport of the seam, as the integer form puts the pydantic-ai transport there. So a test that installs the `web` fake sees each attempt, and the egress check runs at each connect. The policy is a frozen dataclass:

| Field | `SERVICE_READ_RETRY` | Reason |
| --- | --- | --- |
| `attempts` | 4 | The issue asks for a small count. Three waits cover a restart of some seconds. |
| `first_wait_seconds` | 1.0 | The first wait is 1 s to 2 s. |
| `max_wait_seconds` | 8.0 | No single backoff is longer than 8 s plus the jitter. |
| `jitter_seconds` | 1.0 | `wait_exponential_jitter` adds 0 s to 1 s, so two commands do not try again at the same time. |
| `budget_seconds` | 20.0 | No attempt starts after 20 s. The shortest command timeout around a CLI call is the MCP fast timeout, 30 s. A test holds the policy below it. |

The waits of 4 attempts are about 1.5 s, 2.5 s and 4.5 s: 7 s to 10 s in total.

### Which requests and which failures
- Only GET, HEAD and OPTIONS go through the retry loop. RFC 9110 section 9.2.2 makes them idempotent, and the clients of this change read with GET. Every other method goes to the wrapped transport one time.
- The loop sends again after the statuses 429, 502, 503 and 504 (a closed table, `_RETRY_STATUSES`), and after `ConnectError`, `ConnectTimeout`, `ReadError`, `ReadTimeout` and `RemoteProtocolError`. The last one is a read failure: the server closed the connection before its reply, which a pod that stops does.
- A 500 is not sent again. Prometheus gives 500 for an internal error, which a second attempt does not repair. A 4xx other than 429 is not sent again.
- An `SSRFBlockedError` is not an httpx2 error, so the loop raises it at once.

### A transparent transport
When the attempts or the time end, the transport gives the last reply, or raises the last network error, as one attempt does (`retry_error_callback` returns the last outcome). So each client keeps its own check of a status, and it can read the body of the reply. The pydantic-ai transport raises `HTTPStatusError` and closes the reply, so a caller cannot read the `error` field of a 400 (#5487).

The transport closes the reply of each attempt that it sends again (`before_sleep`), so the connection goes back to the pool.

### Waits and the time bound
- The wait is `wait_exponential_jitter(initial=first_wait_seconds, max=max_wait_seconds, jitter=jitter_seconds)`. When the reply has a `Retry-After` header, the wait is the longer of the two (ARCHITECTURE.md section 5). `parse_retry_after` of `devops_cli.github.error_classifier` reads the header.
- The stop is `stop_after_attempt(attempts)`, or the time since the first attempt plus the next wait is at least `budget_seconds`. The time comes from the clock seam `devops_cli.core.clock`. Tenacity's own `stop_before_delay` reads `time.monotonic`, which the `clock` fixture does not fake. A `Retry-After` that is longer than the rest of the budget stops the loop at once.
- The sleep is `clock.sleep`, the seam of docs/TESTING.md.

### The record of the attempts
The transport writes `RequestAttempts(count, seconds)` to the extension `devops_cli.attempts` of the request when it ends, also on an error. httpx2 sets the request on `HTTPStatusError` and on each `RequestError` that leaves the client, so `service_error` reads the record from the error. A request that went through no policy has no record, and the line says 1 attempt.

### One error line
`service_error(service, error, *, setting=None)` maps an `httpx2.HTTPError` to `ServiceRequestError` (`src/devops_cli/exceptions/http.py`, exit status 1). Its message comes from `ERRORS.http`:

`<service> failed after <n> attempts in <s> s: <problem>. <hint>`

The problem is `HTTP <status> <reason>`, with `: <detail>` when the reply holds an error text: the `error` field (with `errorType` before it) or the `message` field of a JSON body, as Prometheus and Grafana give them, or the first line of a `text/plain` body, as Loki gives it. The detail is cut to `CONST_MAX_ERROR_DETAIL_LENGTH`. An HTML body, such as the error page of a tunnel, gives no detail. For a network error it is the class name and the text of the error. The hint is one of a closed table: 429 (wait, then try again), another 4xx (correct the request), a 5xx (the service is not ready; examine its pod), a network error (make sure that the setting is correct and that the pod runs). The line names the service, not its URL.

### The clients
- `PrometheusClient._get_json` uses the policy and maps an `httpx2.HTTPError` with the setting `prometheus.url`. The commands, `critical_alerts` and `_fetch_metric_value` get `ServiceRequestError`. `critical_alerts` puts its message in the gate problem. Its own wait loop does not change.
- `query_loki_metrics` uses the policy and maps both a network error and a status other than 200 with the setting `loki.url`. `execute_loki_query` keeps its contract: a failed connect falls back to `kubectl logs` at once.
- `GrafanaClient` uses the policy for every request, so its GET requests are sent again and its POST requests are not. `_send` maps with the setting `grafana.url`. `sync_dashboard` reads the status of the mapped error to tell a provisioned dashboard apart.
- `get_json` takes `retries`, `SERVICE_READ_RETRY` by default, and maps with the name of the endpoint (`describe_endpoint`, or the host and port of a plain URL). The telemetry panel of the dashboard passes `retries=None`: it falls back to the data of the process at once, and a refresh must not wait 10 s.
- `reaches_service` and the forward poll `_answers` keep one attempt. `reaches_service` must tell an API server that cannot dial the Service (503) from a Service that answers. `forward_service` has its own wait loop around `_answers`.

### The pool key
A pooled client keys on its level, its key and its retry option. `get_json` and `reaches_service` share the key `k8s-proxy:<origin>`, so without the retry option in the key, the first of them would give its transport to the other.

## Rejected alternatives
- **Pass an integer to `retries`, as the AI clients do.** Rejected: the pydantic-ai transport raises `HTTPStatusError` for every 4xx and closes the reply (`create_retry_transport` in `src/devops_cli/ai/retries/__init__.py`), sends again every 5xx, 408 and every method, has no jitter and no time bound, and records failed attempts in the AI spend ledger. Its import takes 0.55 s and 850 modules on each command.
- **Give `create_retry_transport` a policy argument.** Rejected for the same import cost: `HTTPX2TenacityTransport` is in `pydantic_ai.retries`, and importing it loads `pydantic_ai`.
- **Raise `ServiceRequestError` in the transport.** Rejected: the transport does not know the name of the service or its setting, a caller that treats a status itself (Grafana's 400 of a provisioned dashboard, Loki's 400) would lose the reply, and an error that is not an httpx2 error would pass through the `except httpx2.HTTPError` of the callers.
- **Retry in each client with its own loop.** Rejected: four loops with four policies. The issue asks for one policy.
- **Send a 500 again too.** Rejected: the issue limits the statuses to 429, 502, 503 and 504, and a 500 of Prometheus or Grafana is an internal error that a second attempt does not repair.
- **Retry the forward poll and `reaches_service`.** Rejected: each has a contract to report down fast, as the issue allows.
