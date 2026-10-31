# Tasks

## 1. Contract Tests First
- [x] 1.1 Add the contract tests of the plan-only rule to `tests/invariants/test_workflow_contracts.py`: the job `test` has the filter step, the reduced run and the step conditions; a table of sample paths says which are plan-only; a mutation test removes each part. See them fail; verify with `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Update the test of the step `Changed-Line Coverage` in `tests/commands/test_ci.py` for its new condition; verify with `uv run devops ci test tests/commands/test_ci.py`

## 2. Workflow
- [x] 2.1 Add the filter step (it runs only for a pull request with fewer than 3000 files), the permission `pull-requests: read`, the reduced run and the step conditions to the job `test` of `.github/workflows/ci.yml`; verify with `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py`
- [x] 2.2 Check the workflow with `uv run devops ci --check --only actionlint,zizmor`

## 3. Documentation
- [x] 3.1 Name the rule in the CI section of `docs/SDLC.md`; verify with `uv run pytest tests/docs`
- [x] 3.2 Regenerate the documentation with `uv run devops docs generate --sync-readme`

## 4. Verification
- [x] 4.1 Run `uv run devops ci fail-to-pass --base origin/main` and keep its result
- [x] 4.2 Run `uv run devops openspec check` and `uv run devops ci`
