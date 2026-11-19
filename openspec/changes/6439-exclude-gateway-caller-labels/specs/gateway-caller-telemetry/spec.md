## REMOVED Requirements

### Requirement: The gateway drops the caller address and user agent
**Reason**: After the drop, two series that differ only in `client_ip` or `user_agent` collide, and Prometheus refuses about 8 % of the remote-write samples (#6439). LiteLLM now excludes the two labels at the source.
**Migration**: The requirement "The gateway excludes the caller address and user agent at the source" replaces it.

### Requirement: The manifest check runs in the k8s row
**Reason**: The check of the `labeldrop` rules asserted values of a manifest, which `docs/TESTING.md` forbids, and the rules leave the ServiceMonitor (#6439).
**Migration**: The requirement "The label reader checks run in the k8s row" names the two checks that stay.

## ADDED Requirements

### Requirement: The gateway excludes the caller address and user agent at the source
The LLM gateway config SHALL set `litellm_settings.prometheus_exclude_labels` to `client_ip` and `user_agent`, before `litellm_settings.callbacks`. LiteLLM SHALL write no `client_ip` and no `user_agent` label on any `litellm_` series, and SHALL add the counts of all callers into one series, so that no two gateway series collide in Prometheus. The `http` endpoint of the LLM gateway ServiceMonitor SHALL hold no `metricRelabelings` entry.

#### Scenario: The gateway manifests render
- **WHEN** `uv run devops ci --check --only k8s` renders Application `llm`, and a person reads the render
- **THEN** the row passes, the gateway ConfigMap sets `prometheus_exclude_labels` to `client_ip` and `user_agent` before `callbacks`, and the `http` endpoint of ServiceMonitor `llm-gateway` holds no `metricRelabelings`

#### Scenario: The gateway series carry no caller labels
- **WHEN** a person runs `count({job="llm-gateway", client_ip!=""})`, `count({job="llm-gateway", user_agent!=""})` and `count({job="llm-gateway", __name__="litellm_deployment_total_requests_total"})` in Prometheus after the Argo CD sync of Application `llm`
- **THEN** the first two queries return no series, and the third returns a count above 0

#### Scenario: Prometheus refuses no gateway sample
- **WHEN** a person runs `sum(increase(prometheus_remote_storage_samples_failed_total{job="integrations/alloy"}[24h]))` in Prometheus 24 h after the Argo CD sync of Application `llm`
- **THEN** the query gives 0, and `ALERTS{alertname="AlloyRemoteWriteSamplesFailed"}` returns no series

### Requirement: The label reader checks run in the k8s row
The two checks that no dashboard query and no alert expression names `client_ip` or `user_agent` SHALL run in the `k8s` row of `devops ci`, which the Static Analysis check runs.

#### Scenario: The k8s row reports the checks
- **WHEN** `uv run devops ci --check --only k8s` runs the `check_*` functions under `tests/gate/k8s_checks/`
- **THEN** `check_no_dashboard_query_uses_the_dropped_labels` and `check_no_alert_expression_uses_the_dropped_labels` report a pass
