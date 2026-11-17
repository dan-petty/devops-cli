## MODIFIED Requirements

### Requirement: The Crawl4AI alerts have their own rule group
The rule group `crawl4ai` in `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold the warning alerts `Crawl4AIFetchesFailing` and `Crawl4AIUnavailable`. Prometheus SHALL load them with the health `ok`. Each description SHALL point to the section "Crawl4AI" of `docs/CLUSTER.md`.

#### Scenario: The group and the README
- **WHEN** a person runs `uv run devops prometheus rules`
- **THEN** the group `crawl4ai` holds the alerting rules `Crawl4AIFetchesFailing` and `Crawl4AIUnavailable`, each with the health `ok`

## REMOVED Requirements

### Requirement: The text of the fetch alert names the label and the logs
**Reason**: The requirement restates the text of an alert description, and only a test that reads the values file can check it (#6083).
**Migration**: None. The description stays in `k8s/devops/monitoring/prometheus-rules-values.yaml`.
