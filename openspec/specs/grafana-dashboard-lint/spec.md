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

### Requirement: Lint and sync read the environment and the product dashboard folders by default
With no path, `devops grafana dashboards lint` SHALL lint the JSON files of `monitoring/dashboards` of the environment tree and of `k8s/devops/dashboards` in one run, so that a uid that two folders share is an error. It SHALL take one or more paths, and SHALL exit 1 and name a path that does not exist. With no `--dir`, `devops grafana dashboards sync` SHALL sync the JSON files of both folders. A tree with no `monitoring/dashboards` SHALL stop either command.

#### Scenario: Lint with no path
- **WHEN** `devops grafana dashboards lint --json --k8s-dir <tree>` runs in a checkout of devops-cli
- **THEN** the report names each JSON file of `monitoring/dashboards` of the tree and of `k8s/devops/dashboards`

#### Scenario: Sync with no folder
- **WHEN** `devops grafana dashboards sync --k8s-dir <tree>` runs against a Grafana double that accepts each save
- **THEN** it saves one dashboard for each JSON file of both folders, with the uid of the file

#### Scenario: A tree with no dashboard folder
- **WHEN** `devops grafana dashboards sync --dry-run` runs on a tree with no `monitoring/dashboards`
- **THEN** it exits non-zero and names the folder and `--k8s-dir`
