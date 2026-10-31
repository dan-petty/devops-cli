# Tasks

## 1. Expand or refuse a directory argument

Reads: `src/devops_cli/commands/ci.py`, `tests/commands/test_test_selection.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_test_selection.py`.

- [ ] 1.1 Write the tests of the five scenarios of `ci-test-selection` in `tests/commands/test_test_selection.py`, and verify that `uv run devops ci test tests/commands/test_test_selection.py` fails on the directory scenarios and passes on the file scenario
- [ ] 1.2 Add the expansion of directory arguments to `_resolve_test_targets` and the message `directory_without_tests`, and verify that `uv run devops ci test tests/commands/test_test_selection.py` passes
- [ ] 1.3 Update the help text of the `paths` argument, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Remove the workaround in the workflow

Reads: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`, `docs/TESTING.md`, `docs/SDLC.md`.

- [ ] 2.1 Change `PLAN_GATE` in `tests/invariants/test_workflow_contracts.py` to `uv run devops ci test tests/invariants`, and verify that `uv run devops ci test tests/invariants/test_workflow_contracts.py` fails on the old workflow
- [ ] 2.2 Change the step `Plan-Only Invariant Tests` of `.github/workflows/ci.yml` to run `uv run devops ci test tests/invariants`, drop the comment that cites #2868, and verify that `uv run devops ci test tests/invariants/test_workflow_contracts.py` passes
- [ ] 2.3 Write the directory rule in `docs/TESTING.md` and name the new command in `docs/SDLC.md`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
