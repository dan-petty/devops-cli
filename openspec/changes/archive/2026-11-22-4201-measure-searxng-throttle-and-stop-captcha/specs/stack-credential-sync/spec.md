## ADDED Requirements

### Requirement: The SearXNG metrics Secret row comes from the keyring
The cluster Secret push table SHALL declare row `devops/searxng-metrics-auth` with secret type `kubernetes.io/basic-auth`, literal user `searxng` and keyring password `searxng_metrics_password`, and a push SHALL restart `deployment/searxng`.

#### Scenario: The metrics Secret row comes from the keyring
- **WHEN** `uv run devops ci test tests/invariants/test_k8s_searxng.py` runs
- **THEN** the test finds row `devops/searxng-metrics-auth` of type `kubernetes.io/basic-auth` with user `searxng`, password `keyring searxng_metrics_password` and restart `deployment/searxng`, and the test fails before the change
