## MODIFIED Requirements

### Requirement: The devops-cli dashboard shows the embedding cache hit share
The devops-cli dashboard SHALL have the panel "Cache: share of embedding lookups that hit", which divides the embedding cache hits of each window by the lookups of the window, and shows 0 for a window with lookups and no hits. The window SHALL be `$__rate_interval` with a Min step of 15m.

#### Scenario: The panel query
- **WHEN** the panel "Cache: share of embedding lookups that hit" of `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job",result="hit"}[$__rate_interval])) or sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval]))`
- **AND** its Min step is 15m
