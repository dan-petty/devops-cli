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

### Requirement: A target with no refId gets the id that Grafana gives it
The linter SHALL give each target that states no refId the id that Grafana gives it when it loads the panel: the first id in the order A to Z, then AA, AB and so on, that no target of the panel holds. The linter SHALL report a duplicate refId only when two targets of a panel hold the same id after that step.

#### Scenario: Two targets with no refId are no duplicates
- **WHEN** The linter reads a panel with two targets that state no refId.
- **THEN** It reports no "Duplicate target refId" error, because the targets get the ids A and B.

#### Scenario: A stated id is skipped
- **WHEN** The linter reads a panel whose first target states no refId and whose second target states `A`.
- **THEN** The first target gets the id B, and the linter reports no duplicate.

#### Scenario: Two stated ids stay duplicates
- **WHEN** The linter reads a panel with two targets that state `A` and a third that states none.
- **THEN** It reports one error "Duplicate target refId 'A'; a series will be dropped".
