# Tasks

## 1. Remove Test Detection from Product Code
- [ ] 1.1 Remove `PYTEST_CURRENT_TEST` checks from `src/devops_cli/commands/ci.py` and environment pass-through in `src/devops_cli/core/process.py`; verify with `python -c "import os; from devops_cli.commands.ci import _clean_coverage_artifacts"`
- [ ] 1.2 Regenerate documentation with `uv run devops docs generate --sync-readme`

## 2. Extract CI Domain Logic to `ci/`
- [ ] 2.1 Extract gate check specifications, gate cache, and coverage cleanup to `src/devops_cli/ci/`; verify with `uv run pytest tests/ci/`
- [ ] 2.2 Verify test-target selection calls public functions in `src/devops_cli/core/test_selection.py`; verify with `uv run pytest tests/commands/test_test_selection.py`

## 3. Extract Workflow Invariant Tests
- [ ] 3.1 Move committed GitHub workflow assertions from `tests/commands/test_ci.py` to `tests/invariants/test_workflows.py`; verify with `uv run pytest tests/invariants/test_workflows.py`

## 4. Test Files Migration to Edge Fakes
- [ ] 4.1 Migrate `test_workspace.py`, `test_install_tools.py`, `test_uv.py`, and `test_branches.py` to `process_fake` and `cli` fixture; verify with `uv run pytest tests/commands/test_workspace.py tests/commands/test_install_tools.py tests/commands/test_uv.py tests/commands/test_branches.py`
- [ ] 4.2 Migrate `test_test_runner.py`, `test_test_selection.py`, and `test_load_and_pipeline.py` to `process_fake`; verify with `uv run pytest tests/commands/test_test_runner.py tests/commands/test_test_selection.py tests/commands/test_load_and_pipeline.py`
- [ ] 4.3 Dissolve `test_ci.py` and `test_devcontainer.py` into behaviour files; verify with `uv run pytest tests/commands/`

## 5. Verification and Quality Gate
- [ ] 5.1 Verify zero internal patches and zero private imports across migrated test files
- [ ] 5.2 Verify test names conform to ASD-STE100 and do not end in `_success`, `_failure`, `_basic`, or `_command`
- [ ] 5.3 Run `uv run devops openspec check` and `uv run devops ci`

## Workflow follow-up
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
