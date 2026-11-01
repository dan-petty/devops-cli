# Tasks

## 1. Add helm_commands to the dry-run output

Reads: none. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`.

- [ ] 1.1 Write a test in `tests/test_k8s_logging_stack.py` that invokes `deploy-stack --stack logging --dry-run` through the `cli` fixture, parses the JSON output, and asserts that `details.helm_commands` is a list containing: (1) `["helm", "repo", "add", "grafana-community", "https://grafana-community.github.io/helm-charts"]`, (2) `["helm", "repo", "update"]`, and (3) a command list that includes `"loki"`, `"grafana-community/loki"`, `"--version"`, `"20.0.2"`, `"--namespace"`, `"logging"`, `"--values"`, and a path ending in `loki-values.yaml`. The test imports no name starting with `_` from `devops_cli`, and verify that `uv run devops ci test tests/test_k8s_logging_stack.py` fails on the base
- [ ] 1.2 Extract a `_build_helm_repo_cmds(selected_stacks)` function from `_deploy_helm_repos` that returns a `list[list[str]]` of the `helm repo add` and `helm repo update` commands. Refactor `_deploy_helm_repos` to call this builder and then execute each command. In the dry-run branch of `deploy_stack`, call `_build_helm_repo_cmds(selected_stacks)` and `_build_helm_upgrade_cmd(release, helm_ctx, wait, timeout, is_v4=False)` for each release, collect all commands into a list, and add it as `"helm_commands"` in the `details` dict passed to `render_dry_run_result`. Keep the existing `"helm_releases"` key unchanged, and verify that `uv run devops ci test tests/test_k8s_logging_stack.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Update test to read from dry-run output

Reads: none. Changes: `tests/test_k8s_logging_stack.py`.

- [ ] 2.1 The test from the previous group already asserts the chart, version, and repository from the dry-run JSON. Add an assertion that the test module imports no name starting with `_` from `devops_cli`, by checking the module's own imports, and verify that `uv run devops ci test tests/test_k8s_logging_stack.py` fails on the base
- [ ] 2.2 In `tests/test_k8s_logging_stack.py`, remove any import of `_HELM_RELEASES_BY_STACK` or `_HELM_REPOS_BY_STACK` from `devops_cli.commands.k8s.stack_lifecycle`. Replace assertions that read chart, version, or repository from those tables with assertions that read the same values from `details.helm_commands` in the dry-run JSON output, and verify that `uv run devops ci test tests/test_k8s_logging_stack.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
