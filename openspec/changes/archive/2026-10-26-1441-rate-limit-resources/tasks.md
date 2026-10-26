# Tasks

## 1. Specification Tests

- [x] 1.1 Add failing unit tests in `tests/test_gh_cmd.py` asserting that `devops gh rate-limit` and `devops gh rate-limit --format json` start exactly one gh child process with `["api", "rate_limit"]` at the process edge and print every returned resource. Verify failure with `uv run devops ci test tests/test_gh_cmd.py`.

## 2. Implementation

- [x] 2.1 Delete `_enrich_rate_limit_resources`, `_extract_rest_rate_limit_headers`, and `_extract_graphql_rate_limit` in `src/devops_cli/commands/gh.py`.
- [x] 2.2 Update `_parse_rate_limit_payload` in `src/devops_cli/commands/gh.py` to return the payload without enrichment.
- [x] 2.3 Verify `tests/test_gh_cmd.py` passes with `uv run devops ci test tests/test_gh_cmd.py`.

## 3. Documentation and Verification Gate

- [x] 3.1 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` passes.
- [x] 3.2 Run `uv run devops ci fail-to-pass --base origin/main` to verify the failing test evidence.
- [x] 3.3 Run `uv run devops ci` to ensure all quality gates pass.
- [x] 3.4 Archive OpenSpec change with `uv run devops openspec archive 1441-rate-limit-resources`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
