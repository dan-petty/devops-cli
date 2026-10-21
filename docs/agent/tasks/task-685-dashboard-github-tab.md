# Task: GitHub Tab in DevOps Dashboard (#685)

**Issue**: [#685](https://github.com/dan-petty/devops-cli/issues/685)
**Scope**: scope/github
**Feasibility**: Verified against GitHub GraphQL API schema (`Repository.pullRequests`, `Commit.statusCheckRollup`), `gh api rate_limit`, Textual dashboard architecture (`TabbedContent`, `DataTable`, `LogPane`), and `gh run view --log-failed`. Tested with isolated live-edge mocks and unit/reactive tests in `tests/test_github_dashboard.py` and `tests/test_ui_reactive.py`.

## Description

- [x] Opening the GitHub tab works via key `'6'`, `--tab github`, or `--tab 6` on `devops dashboard`.
- [x] The GitHub tab displays open pull requests sorted oldest-first (`createdAt` ascending), showing PR number, title, author, branch, lines (+/-), changed files, unresolved thread count, and check status rollup.
- [x] Banner displays open PR count, count of PRs with failing checks, and core / GraphQL rate limit quotas with time until reset (or `quota unread` on failure).
- [x] Checks rollup counts are accurately classified across check runs and commit status contexts (`fail`, `pending`, `unread`, `cancel`, `skip`, `pass`), displaying `none` when empty and `+` when results are paginated.
- [x] Inspector tab displays PR details, Copilot review state as reported by `pr monitor`, review thread paths with line numbers and author, and full checks table sorted with non-passing checks first.
- [x] Pressing `v` on a failing check linking to `/actions/runs/<run>/job/<job>` invokes `gh run view <run> --job <job> --log-failed --repo <owner/repo>` with a 120s timeout and streams masked output to the Logs tab ending with process exit code. Non-Actions run links show an informative notice.
- [x] Pressing `o` on a PR row or in the inspector opens the pull request in the default browser.
- [x] Dual-timer refresh scheduling: base dashboard domains refresh at `--refresh-interval` (default 5s); GitHub domain refreshes at `max(--refresh-interval, 60s)`. Pressing `r` enforces a 60s cooldown for GitHub refresh, notifying the operator if refreshed too recently.
- [x] Pacing guard prevents excessive sleeps during rate limiting by checking token-bucket pacing before queries and failing closed with an error banner when wait exceeds 5.0s.
- [x] Fail-closed error handling when outside a git repository or GraphQL/REST queries fail.
