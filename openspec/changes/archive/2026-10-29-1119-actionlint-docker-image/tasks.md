# Tasks

## 1. Update tests for the new invocation

- [x] 1.1 Update `tests/test_ci.py`, `tests/test_ci_dry_run.py` and `tests/test_workflow_contracts.py` to match the new `["actionlint"]` invocation, add `shutil.which` mocks, add `test_ci_actionlint_not_on_path`, add the allowlist entry for the `docker://` step, add the `covered_rows` fix, add the digest-parity test, and verify they pass (`uv run pytest tests/test_ci.py tests/test_ci_dry_run.py tests/test_workflow_contracts.py`)

## 2. Implementation of the digest-pinned delivery

- [x] 2.1 Add the `FROM docker.io/kjanat/actionlint:1.17.0@sha256:d484ccca…` stage and `COPY --from` to `.devcontainer/Dockerfile`, remove `actionlint-py` from `pyproject.toml`, regenerate `uv.lock`, change the `CheckSpec` command to `["actionlint"]` and add the `shutil.which` pre-check in `src/devops_cli/commands/ci.py` (`uv run pytest tests/test_ci.py tests/test_ci_dry_run.py tests/test_workflow_contracts.py tests/test_architectural_invariants.py`)
- [x] 2.2 Add the `docker://` actionlint step to the `Static Analysis` job of `.github/workflows/ci.yml` and update the `--skip` list (`uv run pytest tests/test_ci.py tests/test_ci_dry_run.py tests/test_workflow_contracts.py`)

## 3. Documentation

- [x] 3.1 Update `src/devops_cli/ai/knowledge_base/devops_cli/libraries/bandit_actionlint.md` and `python_packages.md` to reflect the new invocation (`uv run devops docs check`)

## 4. Full gate and OpenSpec archive

- [x] 4.1 Verify all tests and static checks pass (`uv run devops ci --check --no-cache --skip test,outdated,actionlint`)
- [x] 4.2 Archive OpenSpec change (`uv run devops openspec archive 1119-actionlint-docker-image`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
