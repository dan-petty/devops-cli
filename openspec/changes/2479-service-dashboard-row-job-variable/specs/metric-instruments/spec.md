## MODIFIED Requirements

### Requirement: The devops-cli dashboard shows the embedding cache hit share
The devops-cli dashboard SHALL have the panel "Embedding Cache Hit Share", which divides the embedding cache hits of the last hour by the lookups of the last hour, and shows 0 for an hour with lookups and no hits.

#### Scenario: The panel query
- **WHEN** the panel "Embedding Cache Hit Share" of `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job",result="hit"}[1h])) or sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[1h])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[1h]))`

### Requirement: The devops-cli dashboard shows the tool calls of the planner
`k8s/monitoring/dashboards/devops-cli.json` SHALL have the row "Planner Tools" with the panel "Planner Tool Calls and Answer Size". The panel SHALL chart the calls of each tool by outcome from `devops_cli_roadmap_tool_calls_total`, and the mean answer size of each tool from `devops_cli_roadmap_tool_answer_chars`. Each query SHALL select `job=~"$job"` and `row="stage"`.

#### Scenario: The dashboard JSON holds the tool panel
- **WHEN** a test reads `k8s/monitoring/dashboards/devops-cli.json`
- **THEN** one panel has a query for `devops_cli_roadmap_tool_calls_total` and a query for `devops_cli_roadmap_tool_answer_chars`, each with `job=~"$job"` and `row="stage"`

#### Scenario: The panel reads each series through the function of its kind
- **WHEN** the dashboard checks read the panel
- **THEN** the counter is the first argument of `increase(`, and the histogram is the first argument of `increase(` inside `histogram_avg(`
