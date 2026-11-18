# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for the environment, the recorded fact and the recorder
  - Verification: `$ uv run devops ci test tests/core/test_git_recording.py`
- [x] 1.2 Isolate the code's git from the host configuration in `Workspace.environment()`
  - Verification: `$ uv run devops ci test tests/core/test_git_contract.py`

## 2. Recording

- [x] 2.1 Record the transcripts again and confirm the `git` row passes
  - Verification: `$ uv run devops ci --check --only git`
