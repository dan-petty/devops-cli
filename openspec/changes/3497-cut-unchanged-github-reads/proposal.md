# Proposal

## Why

Issue #3497: the Service spends most of its GitHub budget on reads. The request counter `devops_cli_github_requests_total` does not tell a 304 answer from a 200 answer, so the share of answers that find no change is not known. The rate limiter also logs each pace line at INFO. These lines wrote 53.6% of a log sample.

## What Changes

- Each paced attempt of the GitHub session counts once, with the HTTP status of its answer in the `status` label. A 304 answer counts with status `304`. An attempt that gets no answer counts with status `none`.
- A gh command counts with status `none`, because gh does not report the HTTP status.
- The two pace lines of the rate limiter, the mandatory pause and the quota window reset, log at DEBUG.
- The counter keeps its name and its total. Every sum over the labels gives the value it gave before.
- The change alters the labels of a metric that a dashboard reads, so it carries a spec delta: two ADDED requirements in `github-api-metrics`.
- This change is the first slice of #3497. It fits one pull request. The refine slice, the cache slice and the scoped intake, stage_ready and idle slices stay open, as the issue asks.

## Capabilities

### Modified Capabilities

- `github-api-metrics`: each paced request names the status of its answer, and the pace lines log at DEBUG.

## Impact

- `src/devops_cli/telemetry/instruments.py`: the description of `devops_cli_github_requests_total` names the status label.
- `src/devops_cli/github/rate_limiter.py`: `acquire` no longer counts a request, and `count_request` counts one with its status. `run_gh` counts each paced attempt with status `none`. The two pace lines log at DEBUG.
- `src/devops_cli/github/session_transport.py`: `pace_request` returns the request labels, and `SessionGitHubAPI._request` counts each attempt with the status of its answer.
- `tests/github/test_github_api_metrics.py`, `tests/github/test_github_rate_limiter.py`.
- `docs/TELEMETRY.md`, regenerated from the instrument description.

## Feasibility

The premise holds at origin/main 0a62030c, checked with these reads:

- `src/devops_cli/telemetry/instruments.py` line 200 to 211: the description of `devops_cli_github_requests_total` names resource, method, repo and row. No status label.
- `src/devops_cli/github/rate_limiter.py` lines 1046 and 1092: both pace lines call `logger.info`.
- `src/devops_cli/github/rate_limiter.py` line 1089: `acquire` emits the counter before the request is sent, so it cannot know the status.
- `src/devops_cli/github/session_transport.py` `SessionGitHubAPI._request`: the answer tuple holds the HTTP status as `answer[0]`, so the session can count it.
- `.venv/lib/python3.14/site-packages/gidgethub/abc.py` lines 186 to 245: a 304 with a stored answer returns the stored data and its next link, and gives the caller only the status.
- The local ledger keeps its charge of a 304, as ADR 0006 records. The metric therefore keeps the 304 attempts in its total.

## Existing Tool Considered

The counter is an instrument that `emit()` sends through the telemetry layer, and the status is a label of that instrument. The change adds no library and no helper. The existing gidgethub conditional request (#983) gives the status of each answer, and prometheus_client gives the label. The change deletes the emit in `acquire` and its `method` parameter, which only the emit used.
