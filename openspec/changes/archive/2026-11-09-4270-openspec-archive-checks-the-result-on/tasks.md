# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests and see them fail on `main`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_archive.py`
- [x] 1.2 Check the result on disk in `archive_change` and plan the dry run in the command
  - Verification: `$ uv run devops ci test tests/openspec tests/core/test_openspec_command.py`

## 2. Documents

- [x] 2.1 Update the help text and regenerate the command documents
  - Verification: `$ uv run devops ci docs`
