## MODIFIED Requirements

### Requirement: The SearXNG metrics Secret row comes from the keyring
The cluster Secret push table SHALL declare row `devops/searxng-metrics-auth` with secret type `kubernetes.io/basic-auth`, literal user `searxng` and the optional keyring password `searxng_metrics_password`, `OPTIONAL_FEATURE_SECRETS` SHALL name the row, and a push SHALL restart `deployment/searxng`. A push that finds no password in the keyring or in the live Secret SHALL skip the password with a warning.

#### Scenario: The metrics Secret row comes from the keyring
- **WHEN** `uv run devops ci test tests/invariants/test_k8s_searxng.py` runs
- **THEN** the test finds row `devops/searxng-metrics-auth` of type `kubernetes.io/basic-auth` with user `searxng`, password `keyring searxng_metrics_password` that is not required, restart `deployment/searxng` and its name in `OPTIONAL_FEATURE_SECRETS`, and the test fails before the change
