# Tasks

## 1. Remove the test hook from pre-commit

- [x] 1.1 Add a failing test that no pre-commit-stage hook runs the test suite (`uv run pytest tests/test_workflow_contracts.py -k no_pre_commit_hook_runs_the_test_suite`)
- [x] 1.2 Remove `devops-ci-test-changed` from `.pre-commit-config.yaml` (`uv run pytest tests/test_workflow_contracts.py tests/test_code_metrics.py tests/test_openspec_scaffold.py tests/test_ruff_complexity_cap.py tests/test_architectural_invariants.py`)
- [x] 1.3 Update the pre-commit diagram and list in `docs/SDLC.md` and the docstring of `src/devops_cli/core/test_selection.py` (`uv run devops docs check`)
- [x] 1.4 Run the gate (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
