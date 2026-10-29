# Tasks

## 1. Re-pin the CI runners to ubuntu-26.04

- [x] 1.1 Point `tests/test_workflow_contracts.py` at `ubuntu-26.04` for the `audit-hardening` job, so it fails while the workflow still names `ubuntu-24.04` (`uv run pytest tests/test_workflow_contracts.py`)
- [x] 1.2 Change the 21 `runs-on: ubuntu-24.04` selections to `ubuntu-26.04` across the eight workflows and remove the obsolete `# moves to ubuntu-26.04 in #1501` markers, so the test passes (`uv run pytest tests/test_workflow_contracts.py tests/test_ci.py`)

## 2. Verify the gate

- [x] 2.1 Confirm the workflow lint passes under the maintained linter and the static gate is green (`uv run devops ci --check --no-cache --skip test,outdated,actionlint`)

## 3. Archive the change

- [x] 3.1 Archive the change (`uv run devops openspec archive 1501-runner-ubuntu-26-04`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
