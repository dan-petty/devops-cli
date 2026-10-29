# Tasks

## 1. The store closes an issue with a reason, after its comment

- [x] Add failing contract tests on both adapters: a close with a comment posts the comment, then closes the issue with the reason; a pull request, a missing issue and a closed issue raise and get no write
  - Verification: `uv run devops ci test tests/test_roadmap_store_contract.py`
- [x] Add failing GitHub store tests: the requests are the read, the comment `POST`, then the `PATCH` with `{"state": "closed", "state_reason": "not_planned"}` on standard input; a refused `PATCH` after a comment raises an error that says the comment is on the issue
  - Verification: `uv run devops ci test tests/test_roadmap_github_store.py`
- [x] Add `RoadmapStore.close`, `issue_close` and `StoreRequests.close`, and apply `state` and `state_reason` in `tests/roadmap_github_fake.py`
  - Verification: `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py`

## 2. `devops gh issues close`

- [x] Add failing command tests: not planned with a comment file, completed with no comment, a comment from standard input, an empty comment, an unknown reason (exit 2, no request), a closed issue, and `--dry-run` (no request, the three requests listed)
  - Verification: `uv run devops ci test tests/commands/test_gh_issues_close.py`
- [x] Add the command, its help and messages, its row in the MCP exposure table, and its name in the help of `devops roadmap intake`
  - Verification: `uv run devops ci test tests/commands/test_gh_issues_close.py tests/test_mcp.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1658-issues-close-reason`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
