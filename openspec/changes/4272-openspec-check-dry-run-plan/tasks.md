# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests and see them fail on `main`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py`
- [x] 1.2 Plan the gate commands in `plan_check`, from the arguments that the real run uses, and print the plan in the dry run of the command
  - Verification: `$ uv run devops ci test tests/openspec tests/core/test_openspec_command.py`

## 2. Documents

- [x] 2.1 Regenerate the command documents for the new messages
  - Verification: `$ uv run devops docs generate --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
