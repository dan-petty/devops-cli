## ADDED Requirements

### Requirement: The items dashboard shows the tool calls of the planner
`k8s/monitoring/dashboards/project-metrics.json` SHALL hold one panel, "Planner Tool Calls and Answer Size". It SHALL chart the calls of each tool by outcome from `devops_cli_roadmap_tool_calls_total`, and the mean answer size of each tool from `devops_cli_roadmap_tool_answer_chars`. Each query SHALL select `job="roadmap-service"` and `row="stage"`.

#### Scenario: The dashboard JSON holds the tool panel
- **WHEN** a test reads `k8s/monitoring/dashboards/project-metrics.json`
- **THEN** one panel has a query for `devops_cli_roadmap_tool_calls_total` and a query for `devops_cli_roadmap_tool_answer_chars`, each with `row="stage"`

#### Scenario: The panel reads each series through the function of its kind
- **WHEN** the dashboard checks read the panel
- **THEN** the counter is the first argument of `increase(`, and the histogram is the first argument of `increase(` inside `histogram_avg(`
