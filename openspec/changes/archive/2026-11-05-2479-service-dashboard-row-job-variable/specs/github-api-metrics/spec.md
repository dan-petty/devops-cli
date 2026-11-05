## MODIFIED Requirements

### Requirement: The devops-cli dashboard shows the GitHub requests
The dashboard `devops-cli.json` SHALL have the row "GitHub API" with a panel for each of these queries: the requests by resource, the throttles by resource, the throttle wait by resource, and the GraphQL points.

#### Scenario: The GitHub API row
- **WHEN** `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** the row "GitHub API" holds the panels "GitHub Requests by Resource", "GitHub Throttles by Resource", "GitHub Throttle Wait by Resource" and "GitHub GraphQL Points"
- **AND** they query `sum by (resource) (increase(devops_cli_github_requests_total{job=~"$job"}[1h]))`, `histogram_count(sum by (resource) (increase(devops_cli_github_throttle_wait_seconds{job=~"$job"}[1h])))`, `histogram_sum(sum by (resource) (increase(devops_cli_github_throttle_wait_seconds{job=~"$job"}[1h])))` and `sum(increase(devops_cli_github_graphql_points_total{job=~"$job"}[1h])) or vector(0)`
