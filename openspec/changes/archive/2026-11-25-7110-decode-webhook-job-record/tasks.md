# Tasks

## 1. Behavior

- [x] 1.1 Write failing webhook cache tests for integer `implement.repair_rounds` in record blocks (`tests/server/routes/test_webhooks_brain.py`)
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py`
- [x] 1.2 Decode webhook job records with `decode_job_record` in `issue_from_event` (`src/devops_cli/roadmap/stores/brain_issues.py`)
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec changes and project gates after implementation
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
