## MODIFIED Requirements

### Requirement: The Crawl4AI alerts have their own rule group
The rule group `crawl4ai` in `k8s/monitoring/prometheus-values.yaml` SHALL hold the warning alerts `Crawl4AIFetchesFailing` and `Crawl4AIUnavailable`. promtool SHALL accept them. Each description SHALL point to the section "Crawl4AI" of `docs/CLUSTER.md`, and that section SHALL list each alert.

#### Scenario: The group and the README
- **WHEN** a test reads the group and the section "Crawl4AI" of `docs/CLUSTER.md`
- **THEN** both alerts have severity `warning`, name the section in the description, and appear in the section
