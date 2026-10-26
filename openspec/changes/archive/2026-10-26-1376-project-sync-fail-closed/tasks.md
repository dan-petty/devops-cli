# Tasks

## 1. Failing tests

- [x] 1.1 Add failing tests for fail-closed field reads, provisioning errors, link failures, and lookup errors in `tests/test_github_projects.py`
  - Verification: `uv run devops ci test tests/test_github_projects.py`

## 2. Fail-closed board lookup and field provisioning implementation

- [x] 2.1 Update `src/devops_cli/github/projects.py` to use `field_list_args` and `FieldListingPayload` for field reads, fail closed on lookups, and route CLI exits through `classify_gh_failure`
  - Verification: `uv run devops ci test tests/test_github_projects.py`
- [x] 2.2 Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Verification and checks

- [x] 3.1 Verify OpenSpec check passes
  - Verification: `uv run devops openspec check`
- [x] 3.2 Verify full CI suite passes
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
