# Tasks

## 1. The drift check asks for its own permissions

Kind: behavior. Reads: `src/devops_cli/github/app_installation.py`, `src/devops_cli/github/onboard/routes.py`, `tests/support/github_repository.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/github/app_installation.py`, `src/devops_cli/k8s/configmap.py`, `tests/github/test_github_app_identity.py`, `tests/commands/test_repos_onboard.py`, `tests/k8s/test_k8s_configmap.py`, `tests/commands/test_config_cmd.py`, `tests/security/test_config_declarations.py`.
Adds: `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS`, `drift_check`

- [x] 1.1 Write the failing tests. In `tests/github/test_github_app_identity.py`, `test_the_drift_check_asks_for_its_own_permissions`: with `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK=true`, the body of the token request is the drift set, with `administration: write` and `contents: write`. In `tests/commands/test_repos_onboard.py`, `test_the_drift_check_with_a_write_token_sends_only_gets`: `devops repos onboard --all --plan` as the App with the variable, over a repository off its baseline, exits 1, the token request holds both write permissions, and each other request is a GET. In `tests/k8s/test_k8s_configmap.py`, `test_the_configmap_leaves_out_the_drift_setting`. Both new tests fail on the base, which asks for the default set
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py tests/commands/test_repos_onboard.py` fails on the base
- [x] 1.2 Rename `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` to `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` with `administration: write` and `contents: write`, and `GitHubAppConfig.read_only` to `drift_check`. Make `configured_app` and `_service_block` of `src/devops_cli/k8s/configmap.py` use the new names, and give the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` in the lists of `tests/commands/test_config_cmd.py` and `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py tests/commands/test_repos_onboard.py tests/k8s/test_k8s_configmap.py tests/commands/test_config_cmd.py tests/security/test_config_declarations.py` passes

## 2. The Job sets the new variable and runs row 4

Kind: other. Reads: `k8s/devops/cronjob-repos-drift.yaml`. Changes: `k8s/devops/cronjob-repos-drift.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/repos_drift_tests.yaml`.

- [ ] 2.1 In `k8s/devops/cronjob-repos-drift.yaml`, set `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` in place of `DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY`, add row 4 to `--only`, and state the permissions in the comments. In the description of `RepositorySettingsUnreadable` and in its promtool fixture, name the permission set of the drift check
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. State the permissions of the drift check

Kind: other. Reads: `docs/CLUSTER.md`, `docs/repos/onboard.md`, `k8s/README.md`, `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`. Changes: `docs/CLUSTER.md`, `docs/repos/onboard.md`, `k8s/README.md`, `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `openspec/specs/repos-drift-alerts/spec.md`.

- [ ] 3.1 Regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` with `devops docs generate`. In `docs/CLUSTER.md` (step 1 and Repository drift), `docs/repos/onboard.md` (The nightly Job), `k8s/README.md` (the row of `RepositorySettingsUnreadable`) and the Status History of ADR 0015, state the drift set with Contents write and Administration write, and that a plan sends GET requests only. Drop "read-only" from the Purpose of `openspec/specs/repos-drift-alerts/spec.md`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 No document, spec or manifest names the old constant, setting or variable
  - Verification: `$ ! git grep -n "READ_TOKEN_PERMISSIONS\|GITHUB_APP_READ_ONLY\|github_app\.read_only\|read-only identity" -- src tests docs k8s openspec/specs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
