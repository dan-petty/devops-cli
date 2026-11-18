# Tasks

## 1. Behavior

- [x] 1.1 Make the gate's version guard the public `version_finding` and call it from `check_openspec`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py`
- [x] 1.2 Read the version in `regenerate` and raise a `ToolExecutionError` before it writes
  - Verification: `$ uv run devops ci test tests/core/test_openspec_command.py`
- [x] 1.3 Add the tests for an older binary, an unreadable version, the message, the shared finding, the environment, the matching binary and the dry run
  - Verification: `$ uv run devops ci test tests/core/test_openspec_command.py`

## 2. Documents

- [x] 2.1 Add the `openspec-regenerate` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
