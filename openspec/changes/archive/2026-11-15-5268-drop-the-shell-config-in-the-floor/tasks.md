# Tasks

## 1. Drop the shell config

Reads: `tests/conftest.py`, `tests/docs/test_docs_source_argv_collector.py`.

Changes: `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`.

- [x] 1.1 Drop the variable at import, and add the floor test.
  - Verification: `$ DEVOPS_CLI_CONFIG=$PWD/config.yaml uv run devops ci test tests/docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
