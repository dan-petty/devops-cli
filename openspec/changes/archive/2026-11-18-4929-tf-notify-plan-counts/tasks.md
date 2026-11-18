# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for a real plan, an import segment, a missing file and an absent
      option.
  - Verification: `$ uv run devops ci test tests/commands/test_tf_notify_plan.py`
- [x] 1.2 Read each count from its own segment and require the plan file.
  - Verification: `$ uv run devops ci test tests/commands/test_tf_notify_plan.py`

## 2. Documents

- [x] 2.1 Update the `tf-notify-plan` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4929-tf-notify-plan-counts`
