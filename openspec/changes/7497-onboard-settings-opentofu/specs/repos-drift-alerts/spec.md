## MODIFIED Requirements

### Requirement: A nightly Job runs the drift check as the App
CronJob `repos-drift` in `k8s/devops/` SHALL run `devops repos onboard --all --plan` once each day in the runner image, one Job at a time and with no retry. It SHALL run only the rows of the command that the token of the drift check can read: rows 0, 3, 4 and 6 to 11. The roots of OpenTofu hold the other settings, and the drift Job of #5328 plans them (ADR 0041).

#### Scenario: The manifest
- **WHEN** `uv run devops ci --check --only k8s` renders and lints `k8s/devops/`
- **THEN** it passes with CronJob `repos-drift` in the render, and its arguments hold `--only 0,3,4,6,7,8,9,10,11`

#### Scenario: A run in the cluster
- **WHEN** a person starts a Job from CronJob `repos-drift` after the deploy
- **THEN** its log holds one report and one state line for each repository of `service.repos`, the reports hold no row 1, 2 or 5, and Prometheus holds the series of `devops_cli_repos_drift_rows{job="repos-drift"}` of each repository
