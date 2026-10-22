# Task: Delete the Dashboard GitHub Tab and the AI Review Panel (#1883)

**Issue**: [#1883](https://github.com/dan-petty/devops-cli/issues/1883)
**Scope**: type/refactor, scope/github
**Feasibility**: The author checked this on 2026-10-22. The author validated both GraphQL queries of `pr_queue.py` offline with `graphql-core` against the public GitHub schema (`schema.docs.graphql`). In that schema, `StatusCheckRollup` has the fields `commit`, `contexts`, `id` and `state`, and no `pageInfo`. Each query gave one error: `Cannot query field 'pageInfo' on type 'StatusCheckRollup'`. No request went to GitHub. The section "Feasibility Evidence" holds the evidence.

## Description

Issue #1883 has two parts. This change is part 1, and it deletes the GitHub tab of `devops dashboard`. Part 2 deletes the AI Review panel. Part 2 is the last part, and it closes the issue.

The GitHub tab never loaded. Both of its queries ask GitHub for `statusCheckRollup { pageInfo }`, and GitHub has no such field. Every refresh showed an error banner. The tab also polled GitHub every 60 seconds, even when another tab was on screen. This change deletes the tab and all code that only the tab used.

- **Source that this change deletes.** The change deletes the file `src/devops_cli/github/pr_queue.py`. It also deletes `GitHubPanel`, the GitHub projections, `GitHubSummary`, the GitHub provider functions and the GitHub refresh timer. The tab, its help text and its key list go with them.
- **Settings that this change deletes.** The change deletes `CONST_DASHBOARD_DOMAIN_GITHUB` and the four `DEFAULT_DASHBOARD_GITHUB_*` defaults. It also deletes the `tab-github` focus entry and the `fetch_github_status` export in `commands/dashboard.py`. The text `6=github` leaves the help of `--tab`.
- **Helpers that go with the tab.** `get_copilot_review_status` in `github/pr_monitor.py` had no other caller. `GitHubRateLimiter.get_all_quotas` had no caller outside the tab and one test. This change deletes both. `sort_prs_oldest_first` stays. It now takes only dictionaries, which is all that `devops pr` gives it.
- **What stays.** `github/check_verdict.py`, `github/run_view.py`, `github/pr_threads.py` and `DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS` stay, because `devops pr` and `devops gh runs view` use them. `telemetry/service_status.py:fetch_github_status` is a different function, and it stays.
- **Tests that this change deletes.** The change deletes `tests/test_github_dashboard.py` (28 tests). It removes the fake GitHub fetcher, the `tab-github` step and the GitHub sample from `tests/test_ui_dashboard.py` and `tests/test_ui_reactive.py`. These tests now expect five domains.
- **Tests that replace two lost guards.** The deleted file held the only test of secret masking in the log of a successful run. `tests/test_gh_cmd.py` now has that test. It checks the masking in `run_view.py` and the timeout that `devops gh runs view` gives to gh. The deleted file also held the only test of the refresh timer. `tests/test_ui_dashboard.py` now has that test, for a positive interval and for an interval of 0.
- **Documents that this change deletes.** The change deletes the task file and the changelog fragment of #685. They describe a tab that no release contains. The change regenerates the CLI documents.
- **What covers the lost features.** `devops gh rate-limit` shows the REST and GraphQL quota. `devops gh runs view <run> --log-failed` shows the log of a failed run. `tests/test_gh_cmd.py` covers both, and it covers `run_view.py` at 100 percent.
- Not done: the deletion of the AI Review panel of `devops dashboard`. It is the last part of #1883. That part closes the issue and adds the changelog fragment `changelog.d/1883.md`.

## Acceptance Criteria

- [x] `devops dashboard` shows five domain tabs and the Logs tab. `--tab 5` is valkey. `tests/test_ui_dashboard.py` and `tests/test_ui_reactive.py` pass with five domains.
- [x] A search of `src/devops_cli/ui/` for `github` finds nothing.
- [x] A search of `src` and `tests` finds no reference to `pr_queue`, `GitHubPanel`, `GitHubSummary`, `CONST_DASHBOARD_DOMAIN_GITHUB`, `DEFAULT_DASHBOARD_GITHUB_*`, `get_copilot_review_status` or `get_all_quotas`.
- [x] `uv run devops docs check` finds no stale generated document.
- [x] The swallowed-failure ceilings and the suppression ceilings need no change. `tests/test_swallowed_failures_ratchet.py` and `tests/test_architectural_invariants.py` pass.
- [x] A test fails when `run_view.py` stops masking secrets, and a test fails when the dashboard starts no refresh timer.
- Pending a person: re-scope or close #805 (release board view in the GitHub tab) and #814 (GitHub API counters for the dashboard). Both need the deleted tab. Only a person runs the mutating roadmap commands while the roadmap Service is suspended.

## Feasibility Evidence

- **The defect.** The queries are `GRAPHQL_PR_QUEUE_QUERY` and `GRAPHQL_SINGLE_PR_QUERY`. Each had one `statusCheckRollup { pageInfo { hasNextPage } }` block, at `pr_queue.py:60-62` and `pr_queue.py:132-134` before the deletion. The `contexts` connection has its own `pageInfo`, and that one is valid.
- **Why no test saw it.** The 28 tests of `tests/test_github_dashboard.py` gave the parser hand-written data. No test sent the query text to a schema.
- **The #685 commit.** Commit `7f61846a` added the tab: 21 files and 1,932 added lines. This change removes its source, its tests and its documents.
- **Callers.** Only `ui/data_providers.py` and `ui/widgets.py` used `pr_queue.py`. A search of `src` and `tests` for each deleted symbol finds no other user.
- **The queue view.** The pinned `gh-dash` tool and its `.gh-dash.yml` belong to a separate item. They are not in this tree at this commit, and this change does not add them.
