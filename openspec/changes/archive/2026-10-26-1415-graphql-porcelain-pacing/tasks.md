# Tasks

## 1. Specification Tests

- [x] 1.1 Add failing unit tests in `tests/test_github_rate_limiter.py` asserting `gh_request_resource` returns `graphql` for porcelain commands (`pr checks`, `pr list`, `issue list`, `release list`, `issue create`, `pr view`, `pr edit`, `pr ready`, `pr close`). Verify failure with `uv run devops ci test tests/test_github_rate_limiter.py`.
- [x] 1.2 Add failing unit tests in `tests/test_github_rate_limiter.py` asserting `gh_request_resource` returns `core` for REST endpoints with substring matches (`repos/graphql/graphql-js/issues`, `repos/octo/research/issues`, `repos/octo/app/contents/docs/search/index.md`, and issue comments mentioning search). Verify failure with `uv run devops ci test tests/test_github_rate_limiter.py`.

## 2. Constants and Implementation

- [x] 2.1 Add `CONST_GH_GRAPHQL_GROUPS`, `CONST_GH_GRAPHQL_PORCELAIN_COMMANDS`, and REST endpoint prefix constants to `src/devops_cli/config/constants.py`.
- [x] 2.2 Refactor `_detect_resource` in `src/devops_cli/github/rate_limiter.py` to use `parse_gh_api_args` and `gh_command_words`. Remove substring predicate helpers.
- [x] 2.3 Verify `tests/test_github_rate_limiter.py` and `tests/test_roadmap_dry_runs.py` pass with `uv run devops ci test tests/test_github_rate_limiter.py`.

## 3. Documentation and Verification Gate

- [x] 3.1 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` passes.
- [x] 3.2 Run `uv run devops ci fail-to-pass --base origin/main` to verify the failing test evidence.
- [x] 3.3 Run `uv run devops ci` to ensure all quality gates pass.
- [x] 3.4 Archive OpenSpec change with `uv run devops openspec archive 1415-graphql-porcelain-pacing`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
