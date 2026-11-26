## MODIFIED Requirements

### Requirement: No query reads the dropped labels
Every query of `k8s/devops/dashboards/ai-spend.json` that reads a `litellm_` series MUST NOT group by or filter on `client_ip` or `user_agent`.

#### Scenario: The dashboards and the alerts ignore the labels
- **WHEN** `uv run devops ci --check --only k8s` reads the target expressions of `ai-spend.json`
- **THEN** no `litellm_` expression names `client_ip` or `user_agent`

### Requirement: The label reader checks run in the k8s row
The check that no query of the spend dashboard names `client_ip` or `user_agent` SHALL run in the `k8s` row of `devops ci`, which the Static Analysis check runs.

#### Scenario: The k8s row reports the checks
- **WHEN** `uv run devops ci --check --only k8s` runs the `check_*` functions under `tests/gate/k8s_checks/`
- **THEN** `check_no_dashboard_query_uses_the_dropped_labels` reports a pass

## REMOVED Requirements

### Requirement: The gateway writes the caller on its series
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Open WebUI calls models only through the gateway
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway excludes the caller address and user agent at the source
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
