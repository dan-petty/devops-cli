# Tasks

## 1. Behavior: a paginated devops gh api read asks for pages of 100

- [x] 1.1 Write failing tests: `session_path` adds `per_page=100` with the rule of gh `addPerPage` and keeps a `per_page` that the endpoint sets
  - Verification: `$ uv run devops ci test tests/github/test_github_api_pages.py`
- [x] 1.2 Write failing command tests: 150 labels with no `per_page` take 2 requests of 100 and `--jq length` prints `100` and `50`, an endpoint with `per_page=50` keeps it, and a dry run plans `per_page=100`
  - Verification: `$ uv run devops ci test tests/commands/test_gh_cmd.py`
- [x] 1.3 Add the page size in `session_path`
  - Verification: `$ uv run devops ci test tests/github/test_github_api_pages.py tests/commands/test_gh_cmd.py`

## 2. Documents

- [x] 2.1 State the page size of the session read of `devops gh api --paginate` in ADR 0006
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
