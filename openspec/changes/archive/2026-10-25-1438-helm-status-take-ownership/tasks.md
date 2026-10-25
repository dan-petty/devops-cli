# Tasks

## 1. Helm version requirement check

- [x] 1.1 Add failing unit tests asserting that Helm 3.16 fails with the version error naming the installed version, and Helm >= 3.17 passes (`uv run devops ci test tests/test_k8s.py`).
- [x] 1.2 Implement `_require_helm_version` in `src/devops_cli/commands/k8s/stack_lifecycle.py` using `packaging.version.Version`, define `CONST_HELM_MIN_VERSION` in `src/devops_cli/config/constants.py`, and invoke the check once in `deploy_stack` (`uv run devops ci test tests/test_k8s.py`).
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. Release status inspection and recovery

- [x] 2.1 Add failing unit tests asserting that `pending-upgrade` or `pending-rollback` releases trigger `helm rollback` before upgrade and `pending-install` releases trigger `helm uninstall` before upgrade (`uv run devops ci test tests/test_k8s.py`).
- [x] 2.2 Implement `_recover_stuck_helm_release` reading `helm status -o json`, running `helm rollback` on `pending-upgrade`/`pending-rollback` and `helm uninstall` on `pending-install`, deleting `_recover_stuck_helm_release_if_pending` and its obsolete tests (`uv run devops ci test tests/test_k8s.py`).
- [x] 2.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 3. Native ownership adoption and cleanup of obsolete code

- [x] 3.1 Add failing unit tests asserting that every `helm upgrade --install` command carries `--take-ownership` (`uv run devops ci test tests/test_k8s.py`).
- [x] 3.2 Add `--take-ownership` to `_build_helm_upgrade_cmd`, delete `_adopt_helm_resource_if_conflict`, `_run_helm_with_adoption_retries`, `CONST_HELM_OWNERSHIP_CONFLICT_RE`, `DEFAULT_HELM_RECOVERY_MAX_RETRIES`, delete obsolete adoption tests in `tests/test_k8s.py`, and reword import error messages in `src/devops_cli/ai/library/introspector.py` and `src/devops_cli/exceptions/ai.py` (`uv run devops ci test tests/test_k8s.py`).
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 4. Quality gate and acceptance criteria validation

- [x] 4.1 Verify acceptance criteria: assert `git grep -En 'another operation|invalid ownership metadata|cannot be imported|CONST_HELM_OWNERSHIP_CONFLICT_RE' src` prints nothing and run static checks (`git grep -En 'another operation|invalid ownership metadata|cannot be imported|CONST_HELM_OWNERSHIP_CONFLICT_RE' src && uv run devops ci --check --only lint,format,actionlint,zizmor`).
- [x] 4.2 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
