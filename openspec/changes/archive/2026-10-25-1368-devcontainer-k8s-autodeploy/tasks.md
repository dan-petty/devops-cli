# Tasks

## 1. Failing tests

- [x] 1.1 Add failing unit test asserting `devops devcontainer bootstrap-k8s` prints the deployment command and resolves with `resolve_devops_argv`, and verify with `uv run pytest tests/test_devcontainer.py -k test_bootstrap_k8s_autodeploy_k8s_stack -n 0`
- [x] 1.2 Update `test_post_start_autodeploy_k8s_stack` to assert spawn arguments without `--deploy`, and update `test_docs_source_argv_collector.py` for removed deploy-stack argv

## 2. Drop auto-deploy implementation

- [x] 2.1 Add `CONST_K8S_MINIKUBE_CONTEXT` in `src/devops_cli/config/constants.py`
- [x] 2.2 Remove `_auto_deploy_k8s_stack` and update `_run_k8s_bootstrap_worker`, `_spawn_background_k8s_bootstrap`, and `bootstrap_k8s_cmd` in `src/devops_cli/commands/devcontainer.py`
- [x] 2.3 Remove `DEVOPS_K8S_AUTO_DEPLOY` from `src/devops_cli/commands/devcontainer.py`, `.devcontainer/devcontainer.json`, and `src/devops_cli/templates/devcontainer.json.j2`
- [x] 2.4 Update messages in `src/devops_cli/lang/en/messages.py` and help strings in `src/devops_cli/lang/en/help.py`
- [x] 2.5 Verify tests pass with `uv run pytest tests/test_devcontainer.py -k "bootstrap or autodeploy" -n 0`

## 3. Documentation and validation

- [x] 3.1 Update `docs/DEVCONTAINER_USAGE.md` to remove auto-deploy references
- [x] 3.2 Regenerate documentation with `uv run devops docs generate --sync-readme`
- [x] 3.3 Validate OpenSpec with `uv run devops openspec check`
- [x] 3.4 Run full verification with `uv run devops ci fail-to-pass --base origin/main`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
