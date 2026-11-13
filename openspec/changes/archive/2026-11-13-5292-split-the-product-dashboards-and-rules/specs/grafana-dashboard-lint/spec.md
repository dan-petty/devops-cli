## ADDED Requirements

### Requirement: Lint and sync read the environment and the product dashboard folders by default
With no path, `devops grafana dashboards lint` SHALL lint the JSON files of `k8s/monitoring/dashboards` and of `k8s/devops/dashboards` of the current directory in one run, so that a uid that two folders share is an error. The command SHALL take one or more paths, each a file or a folder, and SHALL exit 1 and name a path that does not exist. With no `--dir`, `devops grafana dashboards sync` SHALL sync the JSON files of both folders, and SHALL exit 1 and name each folder that does not exist.

#### Scenario: Lint with no path
- **WHEN** `devops grafana dashboards lint --json` runs in the repository root
- **THEN** the report names each JSON file of `k8s/monitoring/dashboards` and of `k8s/devops/dashboards`, and the command exits 0

#### Scenario: Sync with no folder
- **WHEN** `devops grafana dashboards sync` runs in the repository root against a Grafana double that accepts each save
- **THEN** it saves one dashboard for each JSON file of both folders, with the uid of the file
