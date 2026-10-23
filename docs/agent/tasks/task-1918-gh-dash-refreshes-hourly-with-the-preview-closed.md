# Task: gh-dash Refreshes Hourly With the Preview Closed, and the Docs State the Cost (#1918)

**Issue**: [#1918](https://github.com/dan-petty/devops-cli/issues/1918)
**Scope**: type/bug, scope/github
**Feasibility**: Checked on 2026-10-22 against the gh-dash v4.26.2 source. The tag tarball equals the copy that the study used, and `internal/tui/ui.go:732` is the refresh. The request counts in this file follow from `ui.go`, `tabs.go`, `prview.go`, `prapi.go` and `commonapi.go`. The four log lines to count and the file `debug.log` exist in the source. Not checked: the cost in points of each request, which comes from the three `rateLimit(dryRun: true)` calls of the study. No agent started gh-dash. A person counted the log lines of one start on 2026-10-22: the last acceptance criteria give the result.

## Description

The pin of gh-dash (#1882) shipped `.gh-dash.yml` with a refresh every 15 minutes and the preview open. This text calls it the first config. The docs and the task file of #1882 said that this costs about 20 GraphQL points an hour. The source of gh-dash 4.26.2 does not support that number. The first config costs 9 points at start and about 28 points an hour. The GitHub budget is 5,000 GraphQL points an hour for the token, and AI agents use the same token.

This change lowers the recurring cost and states the real numbers:

- **The config.** `.gh-dash.yml` sets `defaults.refetchIntervalMinutes: 60` and `defaults.preview.open: false`. A header comment states the cost. The comments at the two values say what each value does. Every other key stays as it was. The `p` key opens the preview.
- **The test.** `test_the_shipped_config_refreshes_hourly_and_starts_with_the_preview_closed` in `tests/test_gh_dash_config.py` pins the two values. Its docstring names the cost that they protect.
- **The docs.** `docs/DEVCONTAINER_USAGE.md` has three bullets: the cost at start, the cost an hour, and how to measure. The task file of #1882 and its changelog fragment no longer say 15 minutes or 20 points an hour.
- **No custom code.** The change sets two values of the open tool gh-dash. It builds nothing.

The source, the study and one measurement give these numbers:

- **Request counts, from the source.** At start, gh-dash reads the login (1 point) and checks its latest release (1 point, a GraphQL request). It fetches only the sections of the start view, which are the 4 pull request sections. A refresh fetches every section of the view on screen. An open preview fetches the detail of the selected row at start, at each refresh and at each row that a person selects. A closed preview fetches no detail, because `syncSidebar` returns before it sets a row.
- **Cost of one request, from the study.** A pull request section costs 1 point at `limit: 20` and 2 points at `limit: 50`. An issue section costs about 1 point. The detail of a row costs 2 points. This change does not measure these costs again.
- **Totals, from the counts and the costs.** Queue has `limit: 50` (2 points) and three sections have `limit: 20` (3 points), so the sections cost 5 points. With the login and the release check, the start costs 7 points, or 9 points with the preview open. A refresh costs 5 points, or 7 points with the preview open. The first config refreshed 4 times an hour with the preview open, so it cost 28 points an hour. The new config refreshes once an hour with the preview closed, so it costs 5 points an hour.
- **One measurement, with no assigned cause.** A person measured +124 GraphQL points in 22 seconds at the first start with the first config. The first config explains 9 of these points, and the measuring command `devops gh rate-limit` adds 1 point. A later count of the log lines matches the computed cost of about 9 points. The quota counters are shared with every other tool that uses the token. So nobody can assign the jump to gh-dash.

The source gives 4 lines `Fetching PRs` and 1 line `Fetching latest version` at start with the new config. It gives no line `Fetching issues` and no line `Fetching PR `. The login request writes no such line. The count of the first config showed 5 lines `Fetching PRs`, so the new config can also show 5. Outside a clone, gh-dash adds no `repo:` filter to a section. The number of requests stays the same.

Count the lines of `debug.log`. Do not read the quota counters of `devops gh rate-limit` before and after. The rate-limit window can roll between the two reads, and other tools use the same token.

## Acceptance Criteria

- [x] The shipped config refreshes every 60 minutes and starts with the preview closed: `test_the_shipped_config_refreshes_hourly_and_starts_with_the_preview_closed`. It was red on base with `(15, True) == (60, False)`. A change of only the interval to 15 fails it, and a change of only `preview.open` to `true` fails it.
- [x] The header of `.gh-dash.yml` states 7 points at start and 5 points an hour. The file holds only ASCII: `test_the_shipped_config_holds_only_ascii`. The config still breaks no rule of the strict schema, and every other key is as it was.
- [x] `docs/DEVCONTAINER_USAGE.md` states the costs, where each number comes from, the first measurement that has no known cause, and the steps to count the requests.
- [x] The task file of #1882 and `changelog.d/1882.md` read true. They state a refresh every 60 minutes and a closed preview. They keep the first measurement apart from the other numbers.
- [x] `changelog.d/1918.md` records the change. This change does not edit `CHANGELOG.md` or `docs/ROADMAP.md`.
- [x] The tests of the changed files pass offline, and no agent started gh-dash. `devops ci` passes in the pre-push hook before the push.
- [x] A person counted the requests of one start with the first config (refresh every 15 minutes, preview open). The date was 2026-10-22 and the machine was quiet. The command was `gh-dash --debug --config .gh-dash.yml`. It stayed open for 60 seconds and then closed. `debug.log` held 5 lines `Fetching PRs`, 0 lines `Fetching PR `, 0 lines `Fetching issues` and 1 line `Fetching latest version`.
- What matched: the source study expected 0 issue fetches and 1 version check. The log shows both. The counted fetches match the computed cost of about 9 points.
- What did not match: the source study expected 4 section fetches and 1 fetch of the selected row. The log shows 5 section fetches and no fetch of the selected row.
- Not confirmed: the cause of the fifth section fetch. A probable cause is a fetch of the next page when the window gets focus, for a section that has more matches than its limit. Also not confirmed: why the fetch of the selected row did not occur. The preview may not open at start, or the log text may differ.
- The quota counters were not usable. The `graphql` value of `devops gh rate-limit` went from 51 to 7, and the reset time moved by about 10 seconds. So the rate-limit window rolled between the two reads. The `core` value moved by +1. Each run of the measuring command costs 1 core point and 1 GraphQL point.
- The earlier jump of +124 points in 22 seconds cannot be assigned to gh-dash. The counted fetches match the computed cost of about 9 points. The counters are shared with every other tool that uses the token, so they cannot assign a cost to one tool.
- Pending a person: after the merge, run the same 60-second measurement with the new config (refresh every 60 minutes, preview closed). Send the four counts of `Fetching PRs`, `Fetching PR `, `Fetching issues` and `Fetching latest version`. Delete `debug.log`.
- Pending a person: if wanted, find out why a fifth section fetch happens. List the lines `Fetching PRs` of `debug.log` with their queries.

## Deliverables

- [x] `.gh-dash.yml`: the two values, the header comment and the two comments at the values.
- [x] `tests/test_gh_dash_config.py`: the test of the two values.
- [x] `docs/DEVCONTAINER_USAGE.md`: the bullets on the cost at start, the cost an hour and the measurement.
- [x] `docs/agent/tasks/task-1882-pin-gh-dash-and-ship-config.md`: the correction of stale text.
- [x] `changelog.d/1918.md` and the corrected `changelog.d/1882.md`.
