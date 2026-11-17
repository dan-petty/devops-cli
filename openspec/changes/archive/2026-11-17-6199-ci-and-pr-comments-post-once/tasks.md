# Tasks

## 1. The alarm report is in the body of the alarm issue (behavior)

Changes: `src/devops_cli/github/client.py`, `src/devops_cli/ci/job_time.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.

- [x] 1.1 Write failing tests: the client `PATCH`es `issues/<number>` with the body only; a run over the limit with an open alarm issue writes the report into its body and posts no comment; a later run replaces the report and keeps the text of a person; the same report sends no change; the dry run lists the `GET` and the `PATCH` of the issue and no comment
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py tests/github/test_github_client.py`
- [x] 1.2 Add `GitHubClient.update_issue_body`, write the report between marker lines in `raise_alarm`, and change the dry-run plan, the message and the help text
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py tests/github/test_github_client.py`

## 2. One conflict comment for each pull request (behavior)

Changes: `src/devops_cli/roadmap/watch_row.py`.

- [x] 2.1 Write a failing test: a conflict at a new head edits the conflict comment of the older head and posts no comment
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py`
- [x] 2.2 Key the conflict comment on its marker alone
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py`

## 3. One review comment for each pull request and head (behavior)

Changes: `src/devops_cli/ai/review/runner.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/review/review_plans.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.

- [x] 3.1 Write failing tests: a rerun on the same head edits the review comment of that head, or sends no write for the same review; a new head posts a new comment; the dry run lists the `GET` of the comments, the `PATCH` and the `POST`
  - Verification: `$ uv run devops ci test tests/commands/test_review_pr_post.py`
- [x] 3.2 Open the review comment with the marker of the head, edit the comment of the same head, and change the dry-run plan and the help text
  - Verification: `$ uv run devops ci test tests/commands/test_review_pr_post.py`

## 4. Documents

Changes: `docs/TESTING.md`, `docs/CLUSTER.md`, `docs/commands/ci.md`, `docs/commands/review.md`, `docs/commands/ai.md`, `docs/MCP_TOOLS.md`.

- [x] 4.1 Describe the alarm report in the body, the one conflict comment and the one review comment for each head, and regenerate the command reference with `devops docs generate`
  - Verification: `$ uv run devops docs check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
