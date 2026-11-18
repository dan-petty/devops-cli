# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for the hook environment, the gate-row environment, the shells, the install steps, the OSV stub, the recorded limit and the knowledge base
  - Verification: `$ uv run devops ci test tests/invariants/test_uv_malware_check.py`
- [x] 1.2 Run every `devops ci` row command with `UV_MALWARE_CHECK` set to `0`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py`
- [x] 1.3 Set `UV_MALWARE_CHECK` to `0` in the five check-only hooks and the interactive shells, and to `1` in the install steps
  - Verification: `$ uv run devops ci test tests/invariants/test_uv_malware_check.py`

## 2. Documents

- [x] 2.1 Record the uv limit beside `[tool.uv]` and the split in the uv knowledge base
  - Verification: `$ uv run devops ci test tests/invariants/test_uv_malware_check.py`
- [x] 2.2 Add the `uv-malware-check` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
