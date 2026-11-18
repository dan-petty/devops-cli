# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for the tools lock entry and the audit commands
  - Verification: `$ uv run devops ci test tests/tools_lock/test_tools_lock.py`
- [x] 1.2 Override glob and minimatch, write the lock again, and add the tools lock entry and the runner reason
  - Verification: `$ uv run devops ci audit`
- [x] 1.3 Install Style Dictionary in the Design Tokens job with `devops install-tools`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Documents

- [x] 2.1 Name the install and audit paths in docs/DESIGN.md and ADR 0024, and add the Renovate manager
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
