# Proposal

## Why

Issue #3497: the Service spends most of its GitHub budget on reads. The request counter `devops_cli_github_requests_total` does not show whether an answer is a 304 or a 200. So the share of answers that find no change is not known. The rate limiter also logs each pace line at INFO. These lines wrote 53.6% of a log sample.

## What Changes

- Each paced attempt of the GitHub session counts once. Its `status` label holds the HTTP status of its answer. A 304 answer counts with status `304`. An attempt that gets no answer counts with status `none`, and that includes each lost GET that the session sends again.
- A gh command counts with status `none`, because gh does not report the HTTP status.
- The two pace lines of the rate limiter, the mandatory pause and the quota window reset, log at DEBUG.
- The counter keeps its name and its total. Every sum over the labels gives the value it gave before.
- The change adds a label to a metric that operators query. It carries a spec delta: two ADDED requirements in `github-api-metrics`.
- This change delivers criteria 1, 5 and 9 of #3497, and it fits one pull request. The status label comes first, because the other parts need it to measure the share of 304 answers. The other criteria moved to their own issues: #3667 (refine, and the live sum query), #3670 (scoped intake), #3671 (stage_ready) and #3672 (idle poll).

## Capabilities

### Modified Capabilities

- `github-api-metrics`: each paced request names the status of its answer, and the pace lines log at DEBUG.

## Impact

- `src/devops_cli/telemetry/instruments.py`: the description of `devops_cli_github_requests_total` names the `status` label.
- `src/devops_cli/github/rate_limiter.py`: `acquire` no longer counts a request. `count_request` counts one with its status. `run_gh` counts each paced attempt with status `none`. The two pace lines log at DEBUG.
- `src/devops_cli/github/session_transport.py`: `pace_request` returns the request labels. `SessionGitHubAPI._request` reads the token of a GitHub App after the attempt is paced, and counts each attempt with the status of its answer.
- `tests/github/test_github_api_metrics.py`, `tests/github/test_github_app_identity.py`, `tests/github/test_github_rate_limiter.py`.
- `docs/TELEMETRY.md`, regenerated from the instrument description.
- `k8s/README.md`: the Service guide names the `status` label.

## Feasibility

The premise holds at origin/main d254410c, checked on 2026-11-05 with these reads:

- `src/devops_cli/telemetry/instruments.py` lines 200 to 211: the description of `devops_cli_github_requests_total` names resource, method, repo and row. It has no status label.
- `src/devops_cli/github/rate_limiter.py` lines 1046 and 1092: both pace lines call `logger.info`.
- `src/devops_cli/github/rate_limiter.py` line 1089: `acquire` emits the counter before the request is sent, so it cannot know the status.
- `src/devops_cli/github/session_transport.py` `SessionGitHubAPI._request`: the answer tuple holds the HTTP status as `answer[0]`, so the session can count it.
- `.venv/lib/python3.14/site-packages/gidgethub/abc.py` lines 186 to 245: a 304 with a stored answer returns the stored data and its next link. The status of that answer stays 304.
- The local ledger keeps its charge of a 304, as ADR 0006 records. The metric therefore keeps the 304 attempts in its total.
- At origin/main f6d57ecd, after the rebase, `SessionGitHubAPI._request` sends a lost GET again in a loop (#3506). Each attempt of that loop is paced, so each attempt counts.

## Existing Tool Considered

The counter is an instrument that `emit()` sends over OTLP through the telemetry layer. The status is a label of that instrument. The change adds no library. It adds one function, `count_request`, beside the limiter that paces each request. The session already receives the status of each answer. The change deletes the emit in `acquire`, and its `method` parameter, which only the emit used.
