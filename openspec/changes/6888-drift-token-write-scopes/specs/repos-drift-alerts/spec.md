## RENAMED Requirements

- FROM: `### Requirement: A nightly Job runs the drift check with a read-only identity`
- TO: `### Requirement: A nightly Job runs the drift check as the App`

## MODIFIED Requirements

### Requirement: A nightly Job runs the drift check as the App
CronJob `repos-drift` in `k8s/devops/` SHALL run `devops repos onboard --all --plan` once each day in the runner image, one Job at a time and with no retry. Its pod SHALL take only the key `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` of Secret `devops-cli`, SHALL set `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` to `true` and `OTEL_SERVICE_NAME` to `repos-drift`, SHALL mount no ServiceAccount token, and SHALL meet Pod Security `restricted`. It SHALL run only the rows that the token of the drift check can read: rows 0 to 11.

#### Scenario: The manifest
- **WHEN** `uv run devops ci --check --only k8s` renders and lints `k8s/devops/`
- **THEN** it passes with CronJob `repos-drift` in the render

#### Scenario: A run in the cluster
- **WHEN** a person starts a Job from CronJob `repos-drift` after the deploy
- **THEN** its log holds one report and one state line for each repository of `service.repos`, and Prometheus holds the series of `devops_cli_repos_drift_rows{job="repos-drift"}` of each repository
