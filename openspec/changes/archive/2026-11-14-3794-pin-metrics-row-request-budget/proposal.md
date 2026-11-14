# Proposal

## Why

Issue #3794 pins the GitHub request budget of one metrics-row round. The row must stay near its pre-#3601 level of about 222 to 305 requests an hour over a period with two rollouts. The live measurement needs two deployments, so a pull request cannot take it. The offline test in this change pins the five reads of one round with one page of each listing, and fails on a new read or an extra page.

## What Changes

- `src/devops_cli/github/metrics.py` gains `METRICS_ROW_GITHUB_REQUEST_BUDGET = 5`. The constant names the every-issue listing through the session, the CI runs, the milestones, the open issues and the repository metadata through gh. The four traffic reads are skipped under the App.
- `tests/github/test_github_metrics_request_budget.py` runs one metrics-row round over the fake GitHub edges, with the age cache warm and the traffic refusal held, and asserts that the round sends five `devops_cli_github_requests_total` samples under `row="metrics"`.
- The same test seeds a second page of the every-issue listing and asserts that the round sends six samples. Its assertion fails with the recorded count and the budget constant.
- The test runs in the `Tests & Coverage` check that gates merges into `main`.
- No command, option, message, manifest or service behavior changes. The change has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics_request_budget.py`.
- The live two-rollout measurement stays with #3996.

## Feasibility

Checked on `origin/main` 5fbcd0519, 2026-11-14.

- `collect_project_metrics_report` reads the Items through the store's session, then the CI runs, milestones, open-issue taxonomy and repository metadata through gh. The four traffic endpoints return early when GitHub refused the traffic before, as it does under the App.
- `get_item_age_metrics` caches the label times of each Item in `_item_label_times`, so a warm call makes the counted round read no label events.
- The GitHub session counts each REST page in `devops_cli_github_requests_total` (`session_transport.py`), and the rate limiter counts each gh command, both under the active request scope.
- `uv run pytest tests/github/test_github_metrics_request_budget.py` passes: the baseline round sends 5, and the two-page round sends 6 and fails the assertion.

## Existing Tool Considered

No new tool and no library. The test uses pytest, the existing `github_api` fake for the session, `GitHubFake` for gh, `GitFake` for the release tags, and `FakeCollector` for the counter samples. All are open and maintained or already in the repository.
