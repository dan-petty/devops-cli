# Proposal

## Why

Issue #1368: `devops devcontainer bootstrap-k8s` and the devcontainer post-start lifecycle cannot auto-deploy a Kubernetes stack. The child process receives an isolated environment without session bus keys, so the process cannot reach the OS keyring. The call passes no `--context` option, and post-start runs before the D-Bus session bus starts. The owner selected Option B to drop auto-deployment and print the command for manual execution.

## What Changes

- Remove `--deploy/--no-deploy` from `devops devcontainer bootstrap-k8s`.
- Remove `_auto_deploy_k8s_stack` and `MESSAGES.devcontainer.auto_deploy_failed` without a backward compatibility shim.
- Remove `DEVOPS_K8S_AUTO_DEPLOY` from `.devcontainer/devcontainer.json` and `src/devops_cli/templates/devcontainer.json.j2`.
- Remove `HELP.devcontainer.auto_deploy` from `src/devops_cli/lang/en/help.py`.
- Update `_spawn_background_k8s_bootstrap` to omit `--deploy` and `--no-deploy`.
- Update `bootstrap_k8s_cmd` to print `devops k8s deploy-stack --stack <stack> --context minikube` with `CONST_K8S_MINIKUBE_CONTEXT`.
- Add `CONST_K8S_MINIKUBE_CONTEXT` to `src/devops_cli/config/constants.py`.
- Update documentation in `docs/DEVCONTAINER_USAGE.md` and generate CLI documentation.
- The command options and terminal output change, so the change carries a spec delta for `k8s-bootstrap`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-bootstrap`: `devops devcontainer bootstrap-k8s` prints the deployment command and does not auto-deploy Kubernetes stacks.

## Impact

- `src/devops_cli/commands/devcontainer.py`: remove `--deploy/--no-deploy`, `_auto_deploy_k8s_stack`, and print the deploy command.
- `src/devops_cli/config/constants.py`: add `CONST_K8S_MINIKUBE_CONTEXT`.
- `src/devops_cli/lang/en/messages.py`: remove `auto_deploy_failed` and add `bootstrap_k8s_deploy_hint`.
- `src/devops_cli/lang/en/help.py`: remove `auto_deploy` and update `bootstrap_k8s` help.
- `.devcontainer/devcontainer.json`, `src/devops_cli/templates/devcontainer.json.j2`: remove `DEVOPS_K8S_AUTO_DEPLOY`.
- `docs/DEVCONTAINER_USAGE.md`, `docs/CLI_REFERENCE.md`, `docs/commands/devcontainer.md`: update documentation.
- `tests/test_devcontainer.py`, `tests/test_docs_source_argv_collector.py`: update unit tests to assert the printed deployment command and removed options.

## Feasibility

- Confirmed against `src/devops_cli/commands/devcontainer.py` at line 966: `_auto_deploy_k8s_stack` runs `["devops", "k8s", "deploy-stack", "--stack", stack]` with `isolate_env=True`.
- Confirmed against `src/devops_cli/core/process.py` lines 45-96: `DEFAULT_ALLOWED_ENV_VARS` drops `DBUS_SESSION_BUS_ADDRESS`.
- Confirmed on issue #1368 comment: the owner confirmed Option B on 2026-10-25.
- Confirmed `resolve_devops_argv(["k8s", "deploy-stack", "--stack", "infra", "--context", "minikube"])` returns `None`.

## Existing Tool Considered

- `devops k8s deploy-stack` already executes stack deployments, pushes secrets from the keyring, and manages Helm releases.
- We drop custom internal auto-deployment code and print the native command for the user to run.
- Internal code deleted: `_auto_deploy_k8s_stack`, `auto_deploy_failed`, and the `--deploy/--no-deploy` options.
