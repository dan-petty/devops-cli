# Tasks

## 1. deploy-stack reads the chart version from the Application

Kind: behavior. Reads: `src/devops_cli/k8s/environment.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/k8s/crawl4ai_check.py`, `src/devops_cli/commands/k8s/crawl4ai_check.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_environment_root_commands.py`, `tests/support/k8s_commands.py`, `tests/commands/k8s/test_k8s_context.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/gate/k8s_checks/devops_runtime.py`.

- [x] 1.1 Write failing tests: a copy of the tree whose Application `loki` pins `9.8.7` gives `helm upgrade ... --version 9.8.7`, and a tree with no Application for a release stops the deploy and names the release
  - Verification: `$ uv run devops ci test tests/commands/test_environment_root_commands.py`
- [x] 1.2 Read the versions with `chart_versions`, drop the versions of `HELM_RELEASES_BY_STACK`, and drop `CRAWL4AI_IMAGE` and its gate assert
  - Verification: `$ uv run devops ci test tests/commands/test_environment_root_commands.py tests/commands/k8s`

## 2. Delete the tests that assert values of manifests and config

Kind: other. Changes: the test files under `tests/` that read committed config, `tests/fixtures/`, `tests/support/markdown_examples.py`, `tests/support/helm.py`, `tests/support/vale.py`, `src/devops_cli/commands/scan.py`, `tests/invariants/test_source_tree.py`, `tests/module_durations.json`, `tests/gate/tree_checks/config_values.py`, `tests/gate/tree_checks/config_reads.toml`.

- [x] 2.1 Delete each value test and its helpers, fixtures and dead code; keep the gray cases and the tests of code unchanged
  - Verification: `$ uv run devops ci test`
- [x] 2.2 Add the `test-tree` check that refuses a new test that reads a committed config file, with the count of each module
  - Verification: `$ uv run devops ci --only test-tree`
- [x] 2.3 Lower the private import ceiling and drop the deleted modules from the durations file
  - Verification: `$ uv run devops ci test tests/invariants/test_source_tree.py tests/commands/test_ci_shard.py`

## 3. Documents and specs

Kind: other. Changes: `docs/TESTING.md`, `docs/CLUSTER.md`, `docs/SDLC.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, `k8s/README.md`, `k8s/monitoring/dcgm-exporter-values.yaml`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/tools_lock/tools.lock`, `.github/renovate.json`.

- [x] 3.1 State the two test rules in `docs/TESTING.md`, and correct each document that named a deleted test or a pinned version
  - Verification: `$ uv run devops ci docs`
- [x] 3.2 Update the specs that named a deleted test, a deleted capture or a pinned version
  - Verification: `$ uv run devops openspec check`
