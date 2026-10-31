# Tasks

## 1. Contract Tests First
- [x] 1.1 Add the contract tests of the plan-only rule to `tests/invariants/test_workflow_contracts.py`: the job `test` has the filter step, the reduced run and the step conditions; a table of sample paths says which are plan-only; a mutation test removes each part. See them fail; verify with `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Update the test of the step `Changed-Line Coverage` in `tests/commands/test_ci.py` for its new condition; verify with `uv run devops ci test tests/commands/test_ci.py`

## 2. Workflow
- [ ] 2.1 Add the filter step, the permission `pull-requests: read`, the reduced run and the step conditions to the job `test` of `.github/workflows/ci.yml`; verify with `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py`
- [ ] 2.2 Check the workflow with `uv run devops ci --check --only actionlint,zizmor`

## 3. Documentation
- [ ] 3.1 Name the rule in the CI section of `docs/SDLC.md`; verify with `uv run devops ci test tests/docs`
- [ ] 3.2 Regenerate the documentation with `uv run devops docs generate --sync-readme`

## 4. Verification
- [ ] 4.1 Run `uv run devops ci fail-to-pass --base origin/main` and keep its result
- [ ] 4.2 Run `uv run devops openspec check` and `uv run devops ci`

## Workflow follow-up
- `devops ci test <directory>` verifies nothing and exits 0. It is filed as its own issue, not fixed here.
- Pending a person: read the run time of `Tests & Coverage` on the first plan-only pull request after the merge. The goal is under 150 s.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
