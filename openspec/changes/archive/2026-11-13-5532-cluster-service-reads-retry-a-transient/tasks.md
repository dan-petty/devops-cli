# Tasks

## 1. Behavior: the retry policy and the one error line

- [x] 1.1 Write failing tests: a GET is sent again after 429, 502, 503, 504 and a failed connect or read, at most 4 times, with waits that back off with jitter, obey `Retry-After` and stop at the time bound; a 400, a 500, a POST and an egress refusal are sent once; the last reply or error comes back as one attempt gives it; the pool keeps a client with a retry option apart; `service_error` gives one line with the service, the status or the error, the attempts, the time, the hint, and the `error` field of a 4xx body; the budget is less than the MCP fast timeout
  - Verification: `$ uv run devops ci test tests/http/test_retry.py tests/http/test_entry.py`
- [x] 1.2 Add `ReadRetryPolicy`, `SERVICE_READ_RETRY`, `ReadRetryTransport` and `service_error` in `src/devops_cli/http/retry.py`, `ServiceRequestError` in `src/devops_cli/exceptions/http.py`, the messages `ERRORS.http`, and the policy form of `retries` and its pool key in `http_client`
  - Verification: `$ uv run devops ci test tests/http/test_retry.py tests/http/test_entry.py`

## 2. Behavior: the clients of the cluster services

- [x] 2.1 Write failing tests: `PrometheusClient.query` gets the answer after 503, 503, 200 in 3 attempts; `devops prometheus query` prints one line with 4 attempts and exits 1 with no traceback while Prometheus stays down, and prints the `error` field of a 400 after 1 attempt; `query_loki_metrics`, `GrafanaClient` and `get_json` send a GET again after a 503; a Grafana POST is sent once; the forward poll and the telemetry panel send one request; the health gate names the mapped line for a Prometheus that stays down, and its wait goes on through two queries that get no answer
  - Verification: `$ uv run devops ci test tests/prometheus/test_prometheus_client.py tests/commands/test_prometheus.py tests/k8s/test_logql_metrics.py tests/grafana/test_grafana_client.py tests/k8s/test_k8s_service_proxy.py tests/k8s/test_service_probe.py tests/infra/test_nodes.py tests/argo/test_rollouts.py tests/roadmap/test_job_grade_report.py tests/ui/test_ui_telemetry_source.py tests/http/test_http_egress.py`
- [x] 2.2 Use the policy and `service_error` in `PrometheusClient`, `query_loki_metrics`, `GrafanaClient` and `get_json`; catch `ServiceRequestError` in `critical_alerts`, `_fetch_metric_value` and `sync_dashboard`; pass `retries=None` from the telemetry panel of the dashboard
  - Verification: `$ uv run devops ci test tests/prometheus/test_prometheus_client.py tests/commands/test_prometheus.py tests/k8s/test_logql_metrics.py tests/grafana/test_grafana_client.py tests/k8s/test_k8s_service_proxy.py tests/k8s/test_service_probe.py tests/infra/test_nodes.py tests/argo/test_rollouts.py tests/roadmap/test_job_grade_report.py tests/ui/test_ui_telemetry_source.py tests/http/test_http_egress.py`

## 3. Documents

- [x] 3.1 Say in ARCHITECTURE.md section 5 which clients retry a read and how, and in the knowledge base page of httpx2 that `retries` also takes a policy; generate the command reference again with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- A release is necessary: the fix is in the CLI. After the release, a person can stop the Prometheus pod and run `devops prometheus query up` to see the attempts.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
