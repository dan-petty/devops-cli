# Proposal

## Why

Gitea keeps its repositories, its packages and its SQLite database on one `local-path` claim of one worker node, and no copy exists, so a lost disk or node loses the internal work and the images that exist only there. Issue #2144 asks for a scheduled backup off the node with an alert on its age, and for a restore procedure that a person can run and check. This change adds the backup-age alert that Application `prometheus` reads from this repository, the documentation of the Schedule and its target, and the restore procedure, and it names dan-petty/homelab for the environment objects that this repository cannot hold.

## What Changes

- Add the rule group `gitea-backup` with the warning alert `GiteaBackupTooOld` to `k8s/devops/monitoring/prometheus-rules-values.yaml`, so a last successful k8up backup older than 93600 seconds warns, and extend the header comment with the k8up series that the file now watches.
- Add the promtool case `tests/fixtures/prometheus_rules/gitea_backup_tests.yaml`, and add `k8up_jobs_last_successful_timestamp` to `SERVED_SERIES` and the group with its case file to `RULE_GROUP_TESTS` of `tests/prometheus/test_k8s_monitoring_alerting.py`.
- Replace the sentence of the Data subsection of the Gitea section of `k8s/README.md` that says no backup exists with the k8up Schedule `gitea-backup` of dan-petty/homelab, its in-cluster target, its retention, its restic check and the Secret rows that a person pushes.
- Add the row of `GiteaBackupTooOld` to the Alerting table of `k8s/README.md`, and change the sentence above it that calls every product group a group of a `devops_cli_*` series.
- Add the Restore subsection to the Gitea section of `k8s/README.md`, with the S3 method, the folder fallback and the check of the restored repositories and packages.
- Plan no manifest of the environment tree: the k8up release, the Schedule, the PodConfig and the NetworkPolicies are environment paths that the required `k8s` row refuses, so dan-petty/homelab holds them and this repository adds no code that compensates.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `product-monitoring-content`: The Gitea backup age has an alert rule, The product alert rules have their own values file

## Impact

- Code: `k8s/devops/monitoring/prometheus-rules-values.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/fixtures/prometheus_rules/gitea_backup_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/commands/k8s/test_k8s.py`

## Feasibility

- `read_file k8s/README.md` showed `k8s/README.md:1061:Gitea keeps its repositories, its packages and its SQLite database (WAL mode) on the` and `k8s/README.md:1063:There are no backups yet.`, so the premise of the issue holds: the only copy of the Gitea data is on one `local-path` claim, and no backup exists.
- The probes state "The path `k8s/README.md` is a file of the staging commit." and "The path `tests/prometheus/test_k8s_monitoring_alerting.py` is a file of the staging commit.", so the document of the restore procedure and the test module of the rule groups exist at the staged commit.
- The probes state "The path `k8s/gitea/values.yaml` is a file of the staging commit." and "The path `k8s/namespaces.yaml` is a file of the staging commit.", so the Gitea values file and the namespace list of the environment tree exist at the staged commit, and this plan reads them and changes neither.
- `read_file k8s/devops/monitoring/prometheus-rules-values.yaml` showed `k8s/devops/monitoring/prometheus-rules-values.yaml:16:devops_cli_alerting_rules.yml:` and `k8s/devops/monitoring/prometheus-rules-values.yaml:10:A group name is unique over both files.`, so the product rule file exists, holds the one `serverFiles` key, and a new group name must not repeat a name of the environment rules.
- `search_code There are no backups yet` returned one line, `k8s/README.md:1063:There are no backups yet. A branch that a clone pushed is also in that clone, but an issue or a pull request made in Gitea is lost with the node.`, so the sentence to replace is unique in the tree.
- `read_file tests/gate/k8s_checks/environment_freeze.py` showed `tests/gate/k8s_checks/environment_freeze.py:26:_PRODUCT_FOLDERS: Final[tuple[PurePosixPath, ...]] = (`, `tests/gate/k8s_checks/environment_freeze.py:43:and not any(file.is_relative_to(folder) for folder in _PRODUCT_FOLDERS)` and `tests/gate/k8s_checks/environment_freeze.py:44:and file.suffix != _DOCUMENT_SUFFIX`, so a file of `k8s` outside the two product folders `k8s/devops` and `k8s/overlays/homelab/devops` that is no Markdown file is an environment path.
- `tests/gate/k8s_checks/environment_freeze.py:67:f"{_NAME}: {path} is an environment path, and dan-petty/homelab holds the environment."` is the message that the required `k8s` row prints for such a file, and `tests/gate/k8s.py:7:refuses a branch that changes an environment path, until step` shows that the row runs that module on the branch of a pull request.
- `docs/HOMELAB_REPO_SWITCH.md:184:The rule is by folder, so a new environment file is refused too.` shows that a new folder for the k8up release or for the Schedule is an environment path as well, so the plan adds no manifest outside the two product folders.
- `read_spec ci-gate-rows` gave the requirement `The k8s row refuses a change to an environment path`, whose scenario `A new environment file` fails a branch that adds `k8s/new-app/deployment.yaml`, so a pull request of this repository holds no k8up release and no Schedule.
- `k8s/README.md:1304:From this repository, it reads only the product base` shows that Application `prometheus` reads `k8s/devops/monitoring/prometheus-rules-values.yaml` from this repository, so the age alert of the Gitea backup is product content that this change delivers.
- Criterion 1 has two parts: group 1 delivers the age series and the warning alert that Application `prometheus` reads from the product rule file, and the Schedule, the PodConfig and the NetworkPolicies are environment objects of dan-petty/homelab, because `tests/gate/k8s_checks/environment_freeze.py:67:f"{_NAME}: {path} is an environment path, and dan-petty/homelab holds the environment."` is the message of the required `k8s` row for such a file.
- `read_file tests/invariants/test_k8s_manifests.py` showed `tests/invariants/test_k8s_manifests.py:135:def test_readme_lists_the_table`, which reads the Cluster Secrets table of `k8s/README.md`; `src/devops_cli/k8s/cluster_secrets.py` holds the product rows in `CLUSTER_SECRETS: tuple[ClusterSecret, ...] = (`, so the restic password row of namespace `gitea` is an environment row of dan-petty/homelab and this plan adds no product row.
- `k8s/README.md:680:The product rules, the groups that select a` becomes false when the group `gitea-backup` joins the file, so group 2 changes that sentence and the plan modifies the requirement `The product alert rules have their own values file`.
- `tests/prometheus/test_k8s_monitoring_alerting.py:544:def test_each_row_of_the_alerting_table_renders_every_cell` holds each row of the Alerting table to a row that renders every cell, and `k8s/README.md:682:| Alert | Fires when | For | Severity |` gives their order, so group 2 writes the row of `GiteaBackupTooOld` with its 4 cells.
- `read_file tests/prometheus/test_k8s_monitoring_alerting.py` showed `tests/prometheus/test_k8s_monitoring_alerting.py:142:RULE_GROUP_TESTS = (`, `tests/prometheus/test_k8s_monitoring_alerting.py:157:MAX_PROMTOOL_ROUNDS = 1_000` and `tests/prometheus/test_k8s_monitoring_alerting.py:190:SERVED_SERIES = frozenset(`, so the group, its case file and its series join three places of one module, and the 27 rounds of the case stay under 1000.
- `tests/prometheus/test_k8s_monitoring_alerting.py:581:def test_the_promtool_files_of_a_group_test_every_alert_of_the_group` and `tests/prometheus/test_k8s_monitoring_alerting.py:613:def test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` are the two cases that the new pair of `RULE_GROUP_TESTS` must satisfy: the case file tests each alert of the group, and one case fires while another stays quiet.
- `read_file tests/fixtures/prometheus_rules/repos_drift_tests.yaml` showed `tests/fixtures/prometheus_rules/repos_drift_tests.yaml:12:rule_files:` and `tests/fixtures/prometheus_rules/repos_drift_tests.yaml:15:evaluation_interval: 1h`, so the new case file names the group file that the test writes and runs a case of 27 rounds.
- `search_code k8up` returned only `docs/guidelines/production-readiness.md:242:k8up for a volume`, and `search_code GiteaBackupTooOld` returned no match, so this repository holds no k8up release, no k8up Schedule and no such alert yet.
- `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` needs a checkout of the repository, no client of a service and no network; the same holds for `uv run devops ci docs`.
- `uv run devops ci test` starts `uv`, `devops`, `pytest` and `promtool`: the image holds each of them, none is a `NOT_IN_RUNNER` entry, a failure is of class `test`, and the pod settings `runAsNonRoot: true`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true` and `seccompProfile: RuntimeDefault` apply.
- `uv run devops ci docs` starts `uv` and `devops`: the image holds both, neither is a `NOT_IN_RUNNER` entry, a failure is of class `lint`, and the same pod settings apply.
- The live state of the cluster is `not checked`: no tool of this run reads it, so the first live backup and the person's restore run wait for dan-petty/homelab#98 and for the homelab pull request that creates the k8up release and the Schedule.
- The owner's comment of 2026-11-24 adopts `k8up-io/k8up`, and the comment of 2026-11-22 states that dan-petty/homelab#98 makes the bucket `backups-gitea`, its identity and the key Secret.

## Existing Tool Considered

k8up-io/k8up (Apache-2.0, maintained, chart 4.10.1) covers the need: scheduled restic snapshots of a claim to S3-compatible storage, the retention and the prune, an application-aware dump from a pod command, a restic check on a schedule, the backup-age metric and a restore into a namespace. The change builds no backup code of its own, so it carries no build cost.

## Dependencies

- #98: dan-petty/homelab#98 makes the bucket `backups-gitea`, its S3 identity and the key Secret, so the k8up Schedule and the restore have no target before it.
