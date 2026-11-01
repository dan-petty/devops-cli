## ADDED Requirements

### Requirement: dry-run lists helm repo commands
The dry run of `deploy-stack` SHALL list each `helm repo add` command and the `helm repo update` command that the real run makes, in order, with the repository name and URL, under the key `helm_commands` in the `details` dict.

#### Scenario: logging stack dry run shows repo add and update
- **WHEN** A test runs `deploy-stack --stack logging --dry-run` through the `cli` fixture and parses the JSON output
- **THEN** `details.helm_commands` contains `["helm", "repo", "add", "grafana-community", "https://grafana-community.github.io/helm-charts"]` followed by `["helm", "repo", "update"]`

### Requirement: dry-run lists helm upgrade commands
The dry run of `deploy-stack` SHALL list each `helm upgrade --install` command that the real run makes, in order, with the release name, chart, version, namespace, and values file, under the key `helm_commands` in the `details` dict.

#### Scenario: logging stack dry run shows upgrade with chart and version
- **WHEN** A test runs `deploy-stack --stack logging --dry-run` through the `cli` fixture and parses the JSON output
- **THEN** `details.helm_commands` contains a command list that includes `"loki"`, `"grafana-community/loki"`, `"--version"`, `"20.0.2"`, `"--namespace"`, `"logging"`, `"--values"`, and a path ending in `loki-values.yaml`

### Requirement: dry-run commands use real-run builders
The commands in the dry-run `helm_commands` list SHALL be built by the same argument builder functions that the real run uses, so that a change to a builder changes both the dry-run output and the real run.

#### Scenario: builder change reflects in dry run
- **WHEN** A test calls `_build_helm_upgrade_cmd` with the `loki` release dict and compares its result to the corresponding command in the dry-run `helm_commands` list
- **THEN** The two command lists are equal

### Requirement: test reads commands from dry-run output
A test SHALL be able to read the chart, version, and repository from the dry-run output of `deploy-stack` without importing a name starting with `_` from `devops_cli`.

#### Scenario: test reads chart from dry-run JSON
- **WHEN** A test invokes `deploy-stack --stack logging --dry-run` and parses the JSON output
- **THEN** The test finds the chart `grafana-community/loki`, version `20.0.2`, and repository URL in `details.helm_commands`, and the test imports no name starting with `_` from `devops_cli`
