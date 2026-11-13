## MODIFIED Requirements

### Requirement: The devops-cli dashboard shows the embedding cache hit share
The devops-cli dashboard SHALL have the panel "Cache: share of embedding lookups that hit", which divides the embedding cache hits of each window by the lookups of the window, and shows 0 for a window with lookups and no hits. The window SHALL be `$__rate_interval` with a Min step of 15m.

#### Scenario: The panel query
- **WHEN** the panel "Cache: share of embedding lookups that hit" of `k8s/devops/dashboards/devops-cli.json` is read
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job",result="hit"}[$__rate_interval])) or sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval]))`
- **AND** its Min step is 15m

### Requirement: The devops-cli dashboard shows the tool calls of the planner
`k8s/devops/dashboards/devops-cli.json` SHALL have the row "Planner Tools" with the panel "Planner Tool Calls and Answer Size". The panel SHALL chart the calls of each tool by outcome from `devops_cli_roadmap_tool_calls_total`, and the mean answer size of each tool from `devops_cli_roadmap_tool_answer_chars`. Each query SHALL select `job=~"$job"` and `row="stage"`.

#### Scenario: The dashboard JSON holds the tool panel
- **WHEN** a test reads `k8s/devops/dashboards/devops-cli.json`
- **THEN** one panel has a query for `devops_cli_roadmap_tool_calls_total` and a query for `devops_cli_roadmap_tool_answer_chars`, each with `job=~"$job"` and `row="stage"`

#### Scenario: The panel reads each series through the function of its kind
- **WHEN** the dashboard checks read the panel
- **THEN** the counter is the first argument of `increase(`, and the histogram is the first argument of `increase(` inside `histogram_avg(`

### Requirement: The devops-cli dashboard shows the alternatives check
The devops-cli dashboard SHALL have the row "Alternatives Check" with the panels "Alternatives Unchecked Items", "Alternatives Oldest Check Age" and "Alternatives Searches per Check". Each query SHALL read its instrument through the function of its kind: a gauge through `last_over_time`, the histogram through `increase`.

#### Scenario: The queries of the three panels
- **WHEN** the panels of the row in `k8s/devops/dashboards/devops-cli.json` are read
- **THEN** the queries are `sum by (repo) (last_over_time(devops_cli_roadmap_alternatives_unchecked_items{job=~"$job"}[1d]))`, `max by (repo) (last_over_time(devops_cli_roadmap_alternatives_oldest_check_age_seconds{job=~"$job"}[1d]))`, and `histogram_avg(sum by (verdict) (increase(devops_cli_roadmap_alternatives_searches{job=~"$job"}[1d])))` with `histogram_count` of the same selector
