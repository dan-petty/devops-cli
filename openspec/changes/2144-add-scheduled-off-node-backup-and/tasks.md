# Tasks

## 1. Add the Gitea backup age alert and its promtool case

Kind: manifest. Reads: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/repos_drift_tests.yaml`, `tests/commands/k8s/test_k8s.py`. Changes: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/gitea_backup_tests.yaml` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/commands/k8s/test_k8s.py`.

- [ ] 1.1 Add the case `A backup older than 26 hours fires` to `tests/fixtures/prometheus_rules/gitea_backup_tests.yaml`, so `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` fails on the group `gitea-backup` before the rule exists
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 1.2 Add the group `gitea-backup` to `serverFiles.devops_cli_alerting_rules.yml` of `k8s/devops/monitoring/prometheus-rules-values.yaml`: the alert `GiteaBackupTooOld`, the expression `time() - k8up_jobs_last_successful_timestamp{job_type="backup"} > 93600`, `for: 0m`, `severity: warning`, and a summary and a description that name the Gitea section of `k8s/README.md`; extend the header comment with the k8up series that the file now watches. Create `tests/fixtures/prometheus_rules/gitea_backup_tests.yaml` in the shape of `tests/fixtures/prometheus_rules/repos_drift_tests.yaml`: `rule_files` names `gitea_backup.rules.yaml`, `evaluation_interval: 1h`, one case that fires at 27 hours and one that stays quiet at 20 hours, 27 rounds in all. In `tests/prometheus/test_k8s_monitoring_alerting.py` add the group name, the path of the case file, `k8up_jobs_last_successful_timestamp` to `SERVED_SERIES` and the pair of the group and its case file to `RULE_GROUP_TESTS`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 2. Document the Gitea backup, its target and its alert row

Kind: other. Reads: `k8s/README.md`, `k8s/gitea/values.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`. Changes: `k8s/README.md`.

- [ ] 2.1 Replace the sentence `There are no backups yet.` in the Data subsection of the Gitea section of `k8s/README.md` with the backup: the k8up Schedule `gitea-backup` of namespace `gitea`, in dan-petty/homelab, runs the command of the `k8up.io/backupcommand` annotation of the Gitea pod template daily at 02:00 into the bucket `backups-gitea` of the in-cluster SeaweedFS S3 gateway on port 8333, keeps 7 daily and 4 weekly snapshots, prunes weekly and runs a restic check weekly; the S3 key Secret comes with dan-petty/homelab#98, and the restic password is an environment Secret row that a person pushes with `uv run devops k8s push-secrets` before the merge. Change the sentence above the Alerting table that calls every product group a group of a `devops_cli_*` series, and add the row of `GiteaBackupTooOld` to that table: it fires when the last successful k8up backup is older than 26 hours, with no hold and severity warning
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `k8s/README.md`: replace the sentence that says no backup exists, name the k8up Schedule and its in-cluster target, and add the alert row
  - Verification: `$ uv run devops ci docs` passes

## 3. Write the restore procedure and check it on a scratch namespace

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 3.1 Add a Restore subsection to the Gitea section of `k8s/README.md`, after Data, with numbered steps: list the snapshots of the k8up repository, apply a k8up Restore of one snapshot into a scratch namespace with the S3 method, use the folder method for a snapshot that the S3 method cannot read, port-forward the restored Gitea and check the repository list, the packages and one clone, then delete the scratch namespace, and run this check by hand: Run the steps of the Restore subsection once on the homelab cluster after the k8up release and the Schedule of dan-petty/homelab sync: list the snapshots, restore one snapshot into a scratch namespace with the S3 method, use the folder method when the S3 method fails on the signature, port-forward the restored Gitea and check the repository list and one clone, then delete the scratch namespace.
- [ ] 3.2 Edit `k8s/README.md`: add the Restore subsection to the Gitea section. Update `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A scheduled job writes a Gitea backup off the node, and its age is a Prometheus series with an alert when it is older than its limit.
- Group 3: The README has a restore procedure, and a person ran it once on a scratch namespace.
