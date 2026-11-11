# Tasks

## 1. Use a leak marker that no branch name holds

Kind: other. Changes: `tests/ai/rag/test_qdrant_request_telemetry.py`.

- [x] 1.1 Put the marker `..hidden` in the userinfo, the path and the query of the test URLs of `test_upsert_span_names_the_server_by_host_and_port`, and scan every attribute value of the span for `..hidden` and `://`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_telemetry.py`
- [x] 1.2 Do the manual check on a branch whose name holds `token`: in a worktree of this branch, run `git switch -c probe/4358-token-probe`, then `uv run pytest tests/ai/rag/test_qdrant_request_telemetry.py`. All 9 tests pass. On the base, 7 tests fail with the branch name in the assertion. Then run `git switch -` and `git branch -D probe/4358-token-probe`.

## 2. Archive the change

Kind: other. Changes: `openspec/changes/4358-the-qdrant-telemetry-test-reads-the`.

- [x] 2.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`
