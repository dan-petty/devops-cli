# grafana-dashboard-lint Specification

## Purpose
How `devops grafana dashboards lint` checks the queries of the panels of a Grafana dashboard before the dashboard reaches a server: which targets it reads, and which query it refuses.

## Requirements

### Requirement: The linter checks an expression target by its expression
For a target whose datasource type is `__expr__`, the linter SHALL read the query from `expression`, not from `expr`. It SHALL report an empty expression as `Panel target has an empty query`, and it SHALL NOT validate the expression as PromQL. A dashboard that the builders make SHALL have no `expression` key.

#### Scenario: A filled expression
- **WHEN** a panel has two Prometheus targets and a target of datasource type `__expr__` with the expression `$A + $B * 10`
- **THEN** the linter reports no error

#### Scenario: An empty expression
- **WHEN** a target of datasource type `__expr__` has an empty expression
- **THEN** the linter reports the error `Panel target has an empty query`
