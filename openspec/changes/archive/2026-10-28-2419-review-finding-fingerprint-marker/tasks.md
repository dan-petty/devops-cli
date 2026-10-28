# Tasks

## 1. The client reads an issue search

- [x] Add failing tests: a search of two pages is read in full; a page marked incomplete and a search past the result cap raise `GitHubUnreadError`
  - Verification: `uv run devops ci test tests/test_github_client.py`
- [x] Add `GitHubClient.search_issue_bodies`, which reads the search pages by number through the GitHub session
  - Verification: `uv run devops ci test tests/test_github_client.py`

## 2. A filed finding carries its fingerprint, and the review leaves it out

- [x] Add failing tests: the marker round-trips its fingerprints and refuses a value that is no fingerprint; the lookup leaves out the findings that an open, a not planned or a duplicate issue carries and keeps the completed and the unfiled ones; a dry run makes no request and names the search
  - Verification: `uv run devops ci test tests/test_review_filed_findings.py`
- [x] Add `src/devops_cli/review/filed_findings.py` with `finding_marker`, `carried_fingerprints`, `read_filed_findings` and `FiledFindings`
  - Verification: `uv run devops ci test tests/test_review_filed_findings.py tests/test_github_client.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2419-review-finding-fingerprint-marker`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- `devops review intake <session>` calls `read_filed_findings` before its hand-off and writes `finding_marker` into each candidate body: #2420.
