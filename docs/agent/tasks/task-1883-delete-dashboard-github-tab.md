# Task: Delete the Dashboard GitHub Tab and the AI Review Panel (#1883)

**Issue**: [#1883](https://github.com/dan-petty/devops-cli/issues/1883)
**Scope**: type/refactor, scope/github
**Feasibility**: The author checked this on 2026-10-22. The author validated both GraphQL queries of `pr_queue.py` offline with `graphql-core` against the public GitHub schema (`schema.docs.graphql`). In that schema, `StatusCheckRollup` has the fields `commit`, `contexts`, `id` and `state`, and no `pageInfo`. Each query gave one error: `Cannot query field 'pageInfo' on type 'StatusCheckRollup'`. No request went to GitHub. For the AI Review panel, the author read `commands/dashboard.py` and found that `devops dashboard --summary` still calls `fetch_review_status()`, so the provider stays. The author searched the whole repository for every deleted name, and the section "Feasibility Evidence" holds the result.

## Description

Issue #1883 had two parts. Part 1 deleted the GitHub tab of `devops dashboard`. Part 2 deleted the AI Review panel, and it closes the issue. After both parts, `devops dashboard` shows four domain tabs (Kubernetes, Docker, Telemetry and Valkey Cache) and the Logs tab. `--tab 4` is valkey.

### Part 1: the GitHub tab

The GitHub tab never loaded. Both of its queries ask GitHub for `statusCheckRollup { pageInfo }`, and GitHub has no such field. Every refresh showed an error banner. The tab also polled GitHub every 60 seconds, even when another tab was on screen. Part 1 deleted the tab and all code that only the tab used.

- **Source that part 1 deleted.** The file `src/devops_cli/github/pr_queue.py`, `GitHubPanel`, the GitHub projections, `GitHubSummary`, the GitHub provider functions and the GitHub refresh timer. The tab, its help text and its key list went with them.
- **Settings that part 1 deleted.** `CONST_DASHBOARD_DOMAIN_GITHUB` and the four `DEFAULT_DASHBOARD_GITHUB_*` defaults. Also the `tab-github` focus entry and the `fetch_github_status` export in `commands/dashboard.py`. The text `6=github` left the help of `--tab`.
- **Helpers that went with the tab.** `get_copilot_review_status` in `github/pr_monitor.py` had no other caller. `GitHubRateLimiter.get_all_quotas` had no caller outside the tab and one test. Part 1 deleted both. `sort_prs_oldest_first` stays. It takes only dictionaries, which is all that `devops pr` gives it.
- **What stays.** `github/check_verdict.py`, `github/run_view.py`, `github/pr_threads.py` and `DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS` stay, because `devops pr` and `devops gh runs view` use them. `telemetry/service_status.py:fetch_github_status` is a different function, and it stays.
- **Tests that part 1 deleted.** `tests/test_github_dashboard.py` (28 tests), the fake GitHub fetcher, the `tab-github` step and the GitHub sample in `tests/test_ui_dashboard.py` and `tests/test_ui_reactive.py`.
- **Tests that replaced two lost guards.** The deleted file held the only test of secret masking in the log of a successful run. `tests/test_gh_cmd.py` now has that test. It checks the masking in `run_view.py` and the timeout that `devops gh runs view` gives to gh. The deleted file also held the only test of the refresh timer. `tests/test_ui_dashboard.py` now has that test, for a positive interval and for an interval of 0.
- **Documents that part 1 deleted.** The task file and the changelog fragment of #685. They described a tab that no release contains.
- **What covers the lost features.** `devops gh rate-limit` shows the REST and GraphQL quota. `devops gh runs view <run> --log-failed` shows the log of a failed run. The pinned `gh-dash` tool and its file `.gh-dash.yml` show the pull request queue. `tests/test_gh_cmd.py` covers the first two, and it covers `run_view.py` at 100 percent.

### Part 2: the AI Review panel

The panel showed the findings of one review session in a table, with a detail pane and a session picker. It was read-only. It had no key for a verdict, and `devops review verify` is the only way to record one. The panel was a second viewer for data that `devops review findings --details` shows. The owner decided on 2026-10-22 to delete it.

- **Source that part 2 deletes.** `ReviewPanel` in `ui/widgets.py`, with its findings table, its detail pane, its session picker and its `i` key. Seven projections in `ui/projections.py`: `ai_banner`, `ai_rows`, `ai_identities`, `finding_detail`, `review_session_rows`, `review_session_keys` and `finding_records`. The helpers that only `finding_detail` used go with them, and so do `REVIEW_SESSION_COLUMNS`, `CONST_AI_TITLE_MAX_CHARS` and `CONST_FINDING_DETAIL_EMPTY`.
- **The domain and its wiring.** The `ai` domain leaves `ui/refresh.py` and the banner, row and identity registries. `DashboardApp` loses `_fetchers_for`, `_select_review_session` and the review-session state. `refresh_domain` and `refresh_all` lose their `fetchers` argument. The help screen loses the `i` line. `redraw_table` loses its `keep_place` argument, because only the panel set it to false.
- **Settings that part 2 deletes.** `CONST_DASHBOARD_DOMAIN_AI` and its place in `CONST_DASHBOARD_DOMAINS` and `CONST_DASHBOARD_DOMAIN_LABELS`. The whole block "Dashboard Finding Detail" of `config/constants.py` goes: the `CONST_FINDING_DETAIL_*` fields and `CONST_UNICODE_CONTROL_CATEGORY`. The `--tab` help now reads `(1=k8s, 2=docker, 3=telemetry, 4=valkey)`.
- **Provider code that only the panel read.** `list_review_sessions`, `_count_findings`, `ReviewSessionInfo.finding_count`, `ReviewSummary.sessions`, `ReviewSummary.incomplete` and the `session` argument of `fetch_review_status` and `_get_latest_review_session_dir`.
- **What stays.** `fetch_review_status`, `ReviewSummary`, `_listed_sessions` and `_get_latest_review_session_dir` stay, because `devops dashboard --summary` shows the AI Review Findings panel. `format_clean_text_field` stays, because `devops review findings --details` uses it.
- **Tests that part 2 deletes.** The change removes 45 top-level functions of `tests/test_ui_reactive.py`: 38 tests and 7 helpers. It adds 2 functions that replace two of them. The removed tests cover the review banner, rows and keys, `finding_detail`, the session picker and the detail pane. They also cover the session list and the `session` argument of the provider.
- **Tests that part 2 changes.** `test_a_refresh_keeps_the_cursor_and_scroll_of_a_long_table` keeps its horizontal-scroll case, now with a table of long pod names. The provider tests in `tests/test_review_session_store.py`, `tests/test_data_dir_worktrees.py`, `tests/test_review_untrusted_tree.py` and `tests/test_ui_dashboard.py` read the session through `fetch_review_status`. `test_the_board_template_follows_adr_0001` no longer reads a finding-detail constant.
- **Tests that guard the new shape.** `test_the_dashboard_shows_four_domain_tabs_and_the_logs_tab` and `test_the_help_screen_numbers_the_four_domain_tabs_and_lists_no_finding_key` are new. `test_textual_dashboard_app_lifecycle` presses 4 and expects valkey.
- **Documents that part 2 changes.** The change deletes the task file of #834, which described only the detail pane. It removes the pane from the task file of #684. It updates the task files of #519, #739, #771, #972 and #1151 where they named a deleted symbol. It regenerates the CLI documents.
- **What covers the lost features.** `devops review findings` shows the table of findings. `devops review findings --session <name>` opens an older session. `devops review findings --details` prints the full record of each finding. The tuicr item (#1884) plans a tool to read findings next to a diff.
- **What has no replacement.** The panel listed every review session with its status and its finding count. No `devops review` command lists sessions. The option `--session` needs the name of a session, or a part of it. This change accepts the loss, because the owner decided to delete the panel.

## Acceptance Criteria

- [x] `devops dashboard` shows four domain tabs and the Logs tab. `--tab 4` is valkey. `tests/test_ui_dashboard.py` and `tests/test_ui_reactive.py` pass with four domains.
- [x] `devops dashboard --summary` still shows the AI Review Findings panel. `test_cli_dashboard_summary_option` checks this.
- [x] A search of `src/devops_cli/ui/` for `github` finds nothing.
- [x] A search of `src` and `tests` finds no reference to `pr_queue`, `GitHubPanel`, `GitHubSummary`, `CONST_DASHBOARD_DOMAIN_GITHUB`, `DEFAULT_DASHBOARD_GITHUB_*`, `get_copilot_review_status` or `get_all_quotas`.
- [x] A search of the repository outside this task file finds no reference to `ReviewPanel`, `ai_banner`, `ai_rows`, `ai_identities`, `finding_detail`, `review_session_rows`, `review_session_keys`, `finding_records` or `list_review_sessions`.
- [x] The same search finds no reference to `CONST_DASHBOARD_DOMAIN_AI`, `CONST_FINDING_DETAIL_*` or `CONST_UNICODE_CONTROL_CATEGORY`. Two hits stay on purpose: the history in the task file of #1151, and the `tab-ai` text of #690 in `docs/ROADMAP.md`.
- [x] `uv run devops docs check` finds no stale generated document.
- [x] The swallowed-failure ceilings and the suppression ceilings need no change, because no deleted line carried a counted failure or comment. `tests/test_swallowed_failures_ratchet.py` and `tests/test_architectural_invariants.py` pass.
- [x] A test fails when `run_view.py` stops masking secrets, and a test fails when the dashboard starts no refresh timer.
- [x] A test fails when the dashboard shows a tab other than the four domain tabs and the Logs tab.
- [x] A test fails when the help screen names tab 4 as anything but Valkey Cache.
- [x] `refresh_domain` and `refresh_all` take no `fetchers` argument. Only `_fetchers_for` passed it in production, and the change deleted that method. The tests of both functions patch `DOMAIN_FETCHERS` through the `patched_fetchers` fixture.
- Pending a person: read #814 (GitHub API counters for the dashboard) and decide if the deleted tab changes its scope. Its title names the dashboard, and the deleted tab showed the API quota. Only a person runs the mutating roadmap commands while the roadmap Service stays at 0 replicas (#1562).
- Pending a person: re-scope or close #690 (`tab-ai`, the review findings studio of the dashboard). It builds on the AI Review tab that part 2 deleted. Only a person runs the mutating roadmap commands while the roadmap Service stays at 0 replicas (#1562).
- Pending a person: file the issue `fix(dashboard): --tab with an unknown tab ends with a ValueError traceback`. The values `ai` and `5` were valid before this change, and now they end with the traceback. Any other unknown value ended with it before. The fix rejects the value with a typed error that names the four valid tabs.

## Feasibility Evidence

- **The defect.** The queries are `GRAPHQL_PR_QUEUE_QUERY` and `GRAPHQL_SINGLE_PR_QUERY`. Each had one `statusCheckRollup { pageInfo { hasNextPage } }` block, at `pr_queue.py:60-62` and `pr_queue.py:132-134` before the deletion. The `contexts` connection has its own `pageInfo`, and that one is valid.
- **Why no test saw it.** The 28 tests of `tests/test_github_dashboard.py` gave the parser hand-written data. No test sent the query text to a schema.
- **The #685 commit.** Commit `7f61846a` added the tab: 21 files and 1,932 added lines. Part 1 removed its source, its tests and its documents.
- **Callers of the GitHub code.** Only `ui/data_providers.py` and `ui/widgets.py` used `pr_queue.py`. A search of `src` and `tests` for each deleted symbol found no other user.
- **The summary still needs the review provider.** `commands/dashboard.py:142` calls `fetch_review_status()` for the AI Review Findings panel of `--summary`. This is why the provider and `ReviewSummary` stay.
- **Callers of the review provider code.** In `src`, only the deleted projections read `ReviewSummary.sessions` and `ReviewSummary.incomplete`. Only the deleted `_fetchers_for` passed the `session` argument. Only the session table showed `finding_count`. Five test files used `list_review_sessions`, and each now reads the session through `fetch_review_status`.
- **The failing tests first.** Before the source change, `test_textual_dashboard_app_lifecycle` failed with `'tab-ai' == 'tab-valkey'`. The two new tests failed on the tab list (`tab-ai` at index 3) and on the help text.
- **The ceilings.** `python -m tests.test_swallowed_failures_ratchet --lower` changed no ceiling. The `_collect_suppressions` count of every suppression kind equals its ceiling.
- **The queue and finding views.** The pinned `gh-dash` tool and its `.gh-dash.yml` show the queue. `devops review findings --details` shows a finding. Neither needs the dashboard.
