# Proposal

## Why

#2469: `deploy-stack --dry-run` gives only release names in `details.helm_releases`. It does not list the `helm repo add` or `helm upgrade --install` commands. A person cannot check the chart, version, and repository from the output. Tests must read the private tables `_HELM_RELEASES_BY_STACK` and `_HELM_REPOS_BY_STACK`, which violates the rule in docs/TESTING.md that no test imports a private name.

## What Changes

- Add a `helm_commands` key to the dry-run `details` dict of `deploy-stack`, holding the full argument lists of each `helm repo add`, `helm repo update`, and `helm upgrade --install` command.
- Extract a `_build_helm_repo_cmds` function so both the dry-run and real-run paths build repo commands from the same code.
- Call `_build_helm_upgrade_cmd` in the dry-run branch to build each upgrade command.
- Keep the existing `helm_releases` key for backward compatibility.
- Add a test that reads chart, version, and repository from the dry-run JSON output without importing a private name.
- Update `tests/test_k8s_logging_stack.py` to read from the dry-run output instead of the private tables.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-helm-deploy`: dry-run lists helm repo commands, dry-run lists helm upgrade commands, dry-run commands use real-run builders, test reads commands from dry-run output

## Impact

- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py`
- Tests: `tests/test_k8s_logging_stack.py`

## Feasibility

- The premise is confirmed in `src/devops_cli/commands/k8s/stack_lifecycle.py`: the dry-run branch of `deploy_stack` calls `render_dry_run_result` with `"helm_releases": [r["name"] for r in all_releases]` and calls no `render_request_plan` for helm. The real-run path calls `_deploy_helm_repos` and `_build_helm_upgrade_cmd`, both visible in the same file.
- The tables `HELM_REPOS_BY_STACK` and `HELM_RELEASES_BY_STACK` are defined at module level in the same file, with the `logging` stack holding one repo (`grafana-community`) and one release (`loki`, chart `grafana-community/loki`, version `20.0.2`).
- First checks the implementation runs against the real system: `uv run devops k8s deploy-stack --stack logging --dry-run` to confirm the current output lacks `helm_commands`, and `uv run pytest tests/test_k8s_logging_stack.py` to confirm the existing test reads private tables.

## Existing Tool Considered

No open, maintained library covers this need. The dry-run mechanism (`render_dry_run_result` in `src/devops_cli/dry_run.py`) and the argument builders (`_deploy_helm_repos`, `_build_helm_upgrade_cmd` in `src/devops_cli/commands/k8s/stack_lifecycle.py`) are project-specific code. The fix calls the existing builders in the dry-run path and adds their output to the `details` dict. The written cost is the tokens to extract `_build_helm_repo_cmds`, edit the dry-run branch of `deploy_stack`, add the command list to `details`, and update one test file. The elapsed time is under one hour of focused work. No internal code is deleted; `_deploy_helm_repos` is refactored to call the new builder.
