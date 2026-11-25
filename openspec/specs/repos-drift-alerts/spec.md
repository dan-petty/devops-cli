# repos-drift-alerts Specification

## Purpose
The nightly Job that runs the drift check of the repository settings, `devops repos onboard --all --plan`, as the GitHub App with the permissions of the drift check, and the alert rules that tell an operator when a repository of `service.repos` is off its baseline, when the check cannot read a row, and when the check stops (#6783, ADR 0035).

## Requirements

### Requirement: A nightly Job runs the drift check as the App
CronJob `repos-drift` in `k8s/devops/` SHALL run `devops repos onboard --all --plan` once each day in the runner image, one Job at a time and with no retry. It SHALL run only the rows that the token of the drift check can read: rows 0 to 11.

#### Scenario: The manifest
- **WHEN** `uv run devops ci --check --only k8s` renders and lints `k8s/devops/`
- **THEN** it passes with CronJob `repos-drift` in the render

#### Scenario: A run in the cluster
- **WHEN** a person starts a Job from CronJob `repos-drift` after the deploy
- **THEN** its log holds one report and one state line for each repository of `service.repos`, and Prometheus holds the series of `devops_cli_repos_drift_rows{job="repos-drift"}` of each repository

### Requirement: The pod of the drift check holds only the App key
The pod of CronJob `repos-drift` SHALL take only the key `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` of Secret `devops-cli`, SHALL set `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` to `true` and `OTEL_SERVICE_NAME` to `repos-drift`, SHALL mount no ServiceAccount token, and SHALL meet Pod Security `restricted`.

#### Scenario: The pod spec
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops/`
- **THEN** the pod of CronJob `repos-drift` reads one key of Secret `devops-cli`, sets the two variables, has `automountServiceAccountToken: false`, and passes the Pod Security check

### Requirement: The drift alerts have their own rule group
The rule group `repos-drift` in `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold the warning alerts `RepositorySettingsDrift`, `RepositorySettingsUnreadable` and `RepositoryDriftCheckStopped`. Each selector SHALL name `job="repos-drift"`. promtool SHALL accept them, and the alert table of `k8s/README.md` SHALL have a row for each, with its action.

#### Scenario: The group
- **WHEN** `promtool check rules` reads the rule files of the server
- **THEN** it accepts the group `repos-drift`

### Requirement: A repository off its baseline warns
`RepositorySettingsDrift` SHALL fire for a repository when the last value in the last 2 days of its series `state="drift"` is above 0. It SHALL stay quiet when a later run set 0.

#### Scenario: A drift row
- **WHEN** `promtool test rules` evaluates a `drift` series of 2 of one repository
- **THEN** `RepositorySettingsDrift` fires with the label `repo` of the repository

#### Scenario: A later clean run
- **WHEN** `promtool test rules` evaluates a `drift` series that goes from 2 to 0
- **THEN** `RepositorySettingsDrift` stays quiet after the 0

#### Scenario: A run of a workstation
- **WHEN** `promtool test rules` evaluates a `drift` series of 2 with `job="devops-cli"`
- **THEN** `RepositorySettingsDrift` stays quiet

### Requirement: A row that the check cannot read warns on its own
`RepositorySettingsUnreadable` SHALL fire for a repository when the last value in the last 2 days of its series `state="not_readable"` is above 0. A not readable row SHALL NOT fire `RepositorySettingsDrift`.

#### Scenario: A not readable row
- **WHEN** `promtool test rules` evaluates a `not_readable` series of 7 and a `drift` series of 0 of one repository
- **THEN** `RepositorySettingsUnreadable` fires, and `RepositorySettingsDrift` stays quiet

### Requirement: A check that stops warns
`RepositoryDriftCheckStopped` SHALL fire when the Job sent a value of `devops_cli_repos_drift_rows` in the last 7 days but none in the last 2 days. It SHALL stay quiet before the first run.

#### Scenario: The runs stop
- **WHEN** `promtool test rules` evaluates a series with a value each day for 3 days and then no value for 2 days
- **THEN** `RepositoryDriftCheckStopped` fires

#### Scenario: No run yet
- **WHEN** `promtool test rules` evaluates no series of the Job
- **THEN** `RepositoryDriftCheckStopped` stays quiet
