# Tasks

## 1. Behavior

- [x] 1.1 Name the gh command, its exit code and its stderr in the error of a failed roadmap store write
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_writes.py`
- [x] 1.2 Name the full issue title in the `create_issue` error and in the intake failure summary
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_write_failures.py`

## 2. Documents

- [x] 2.1 Add the `roadmap-store-write-failure` capability and extend `roadmap-intake-failures`
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
