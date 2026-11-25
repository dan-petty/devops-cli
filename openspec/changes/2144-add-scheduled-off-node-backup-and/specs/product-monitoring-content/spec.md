## ADDED Requirements

### Requirement: The Gitea backup age has an alert rule
The rule group `gitea-backup` in `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold the warning alert `GiteaBackupTooOld`, whose expression SHALL fire when `time() - k8up_jobs_last_successful_timestamp{job_type="backup"}` is more than 93600 seconds, and `tests/prometheus/test_k8s_monitoring_alerting.py` SHALL list that series in `SERVED_SERIES` and the group with its case file in `RULE_GROUP_TESTS`.

#### Scenario: An old backup warns and a fresh one stays quiet
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the case of a last successful backup 27 hours old fires `GiteaBackupTooOld` with severity warning, and the case of a backup 20 hours old keeps it quiet

## MODIFIED Requirements

### Requirement: The product alert rules have their own values file
`k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold only `serverFiles.devops_cli_alerting_rules.yml`, with each rule group that watches a series of this product, and with the group `gitea-backup` that watches the k8up backup series. Each group that selects a `devops_cli_` series SHALL be in this file, and no environment group SHALL select one.

#### Scenario: The product file holds the groups that watch a devops_cli series
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the product file holds the group `gitea-backup` beside the groups that select a `devops_cli_` series, and no group of the environment values file selects one
