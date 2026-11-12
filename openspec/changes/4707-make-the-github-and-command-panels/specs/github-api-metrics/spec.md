## MODIFIED Requirements

### Requirement: The devops-cli dashboard shows the GitHub requests
The dashboard `devops-cli.json` SHALL have the row "GitHub API" with these panels: the core requests that cost quota in each hour by job, with the answers 304 as a separate series and the Service budget limit as a reference line; the requests of the other resources in each hour; the throttles in the range as a stat; the throttles and their wait by resource in the range as a table; and the GraphQL points in each hour by job, with a reference line at 5,000 points. The hourly panels SHALL show bars with a Min interval of 1h.

#### Scenario: The GitHub API row
- **WHEN** `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** the row "GitHub API" holds the panels "GitHub quota: core requests per hour", "GitHub quota: requests of the other resources per hour", "Throttles: count in the range", "Throttles: count and wait by resource in the range" and "GitHub quota: GraphQL points per hour"
- **AND** the core panel queries `round(sum by (job) (increase(devops_cli_github_requests_total{job=~"$job",resource="core",status!="304"}[$__interval])))` and `round(sum(increase(devops_cli_github_requests_total{job=~"$job",resource="core",status="304"}[$__interval])))`

#### Scenario: The throttles in the range
- **WHEN** promtool evaluates the throttle panels over 24 h on a fixture histogram with 3 core throttles of 35 s and 1 graphql throttle of 5 s
- **THEN** the stat gives 4, and the table gives 3 and 35 s for core and 1 and 5 s for graphql
