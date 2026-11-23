# Tasks

## 1. The drift check reports the state of each repository

Kind: behavior. Reads: `src/devops_cli/commands/repos.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/telemetry/instruments.py`, `tests/support/github_repository.py`, `tests/support/fakes/otlp.py`. Changes: `src/devops_cli/github/onboard/drift.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/commands/test_repos_onboard.py`.
Adds: `DriftState`, `drift_counts`, `record_drift`, `REPOS_DRIFT_ROWS`

- [x] 1.1 Write the failing tests `test_a_pending_change_gives_the_drift_report`, `test_no_change_gives_no_drift_report`, `test_a_row_that_is_not_readable_gives_its_own_state` and `test_one_repository_sets_no_drift_gauge` in `tests/commands/test_repos_onboard.py`, one for each scenario of the requirements "The drift check reports the state of each repository" and "The drift check prints the state of each repository". Read the gauge from the `otlp` fixture by its name, so the tests import no name that the change adds. They fail on the base, which sets no gauge and prints no state line
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` fails on the base
- [x] 1.2 Add the gauge `REPOS_DRIFT_ROWS` (`devops_cli_repos_drift_rows`) to `src/devops_cli/telemetry/instruments.py`. Add `src/devops_cli/github/onboard/drift.py` with `DriftState`, `drift_counts(report)` and `record_drift(report)`, which sets both series of the repository with its `RepoRef` key. In `onboard` of `src/devops_cli/commands/repos.py`, with `--all`, record each report and print the state line of each repository after the reports, with a text of `MESSAGES.repos`
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` passes

## 2. The preflight of the App reads no user

Kind: behavior. Reads: `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/core/process.py`, `tests/github/test_github_app_identity.py`. Changes: `src/devops_cli/github/onboard/settings_rows.py`, `tests/support/github_repository.py`, `tests/commands/test_repos_onboard.py`.

- [x] 2.1 Make `RepositoryState` of `tests/support/github_repository.py` refuse `GET /user` with HTTP 403 to an installation token, as GitHub does. Write the failing test `test_the_drift_check_as_the_app_reads_no_user` in `tests/commands/test_repos_onboard.py` for the scenario "The drift check as the App". It fails on the base, where `token_scopes` raises on the 403 before row 0
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` fails on the base
- [x] 2.2 In `token_scopes` of `src/devops_cli/github/onboard/settings_rows.py`, give None with no request when the identity of the session is the App
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py tests/github/onboard/test_onboard_rows.py` passes

## 3. A read-only token asks for read permissions only

Kind: behavior. Reads: `src/devops_cli/github/app_installation.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/k8s/configmap.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/github/app_installation.py`, `src/devops_cli/k8s/configmap.py`, `tests/github/test_github_app_identity.py`, `tests/k8s/test_k8s_configmap.py`.
Adds: `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`

- [x] 3.1 Write the failing test `test_a_read_only_process_asks_for_a_token_with_read_permissions_only` in `tests/github/test_github_app_identity.py` for the scenario "The token request of a read-only process", and the test `test_the_configmap_leaves_out_the_read_only_setting` in `tests/k8s/test_k8s_configmap.py` for the scenario "The ConfigMap leaves out the read-only setting". The first fails on the base, which ignores the setting
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` fails on the base
- [x] 3.2 Add `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` to `src/devops_cli/config/constants.py`, the setting `read_only` to `GitHubAppConfig`, and give the App those permissions in `configured_app` when the setting is true. Leave the setting out of the `service.github_app` of the ConfigMap in `src/devops_cli/k8s/configmap.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py tests/k8s/test_k8s_configmap.py` passes

## 4. The nightly Job and its alerts

Kind: other. Reads: `k8s/devops/cronjob-stage.yaml`, `k8s/devops/renovate/cronjob.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/devops/cronjob-repos-drift.yaml`, `k8s/devops/kustomization.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `k8s/argocd/image-updater-values.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/repos_drift_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [ ] 4.1 Add CronJob `repos-drift` in `k8s/devops/cronjob-repos-drift.yaml`, name it in `k8s/devops/kustomization.yaml` and in `PRODUCT_MANIFESTS_BY_STACK` of `src/devops_cli/commands/k8s/stack_lifecycle.py`, and name it in the comment of the runner image of `k8s/argocd/image-updater-values.yaml`
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [ ] 4.2 Add the rule group `repos-drift` with its three alerts, its promtool cases in `tests/fixtures/prometheus_rules/repos_drift_tests.yaml`, and the group and the served series in `tests/prometheus/test_k8s_monitoring_alerting.py`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 5. Documents

Kind: other. Reads: `docs/repos/onboard.md`, `docs/CLUSTER.md`, `k8s/README.md`. Changes: `docs/repos/onboard.md`, `docs/CLUSTER.md`, `k8s/README.md`, `docs/TELEMETRY.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [ ] 5.1 Tell the nightly Job, its rows and its gauge in `docs/repos/onboard.md`, add the section "Repository drift" to `docs/CLUSTER.md`, add the rows of the three alerts to the alert table of `k8s/README.md`, and regenerate the documents with `devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: deploy the stack `devops` after the merge, then start one Job with `kubectl -n devops create job --from=cronjob/repos-drift repos-drift-manual` and read its log.
- Pending a person: the rows that read the baseline stay `not readable` until dan-petty/devtools pull request 43 merges and Renovate updates the base of the runner image.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
