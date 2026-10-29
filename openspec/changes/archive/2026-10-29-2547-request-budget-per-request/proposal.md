# Proposal

## Why

Issue #2547: the Service's hourly GitHub budget (`RequestBudget`) counts requests only when a round ends, and it only stops a new round from starting.
A round that starts under the budget sends all its requests. A round that is still running when the pod stops never reaches `record_round`, so its requests are not in the record.
In one hour the Service sent about 913 requests against a budget of 500.

## What Changes

- `RequestBudget` gives each request its place in a sliding window with `admit`. It no longer reads a count of requests at the end of a round.
- `GitHubRateLimiter.acquire` calls a request gate before it paces a request. The Service installs `RequestBudget.admit` as the gate when it starts and removes it when it stops. This covers `run_gh` and the GitHub session.
- A request that the window has no room for waits until the oldest request leaves the window. When the Service stops, the budget is closed, and such a request ends with an error.
- `admit` writes the budget record each time. The record keeps its format, one `[time, count]` pair for each request.
- Remove `RequestCounter`, `process_request_count` and the `request_counter` argument of `ServiceManager`.

## Capabilities

### Modified Capabilities

- `roadmap-service-limits`: the budget is checked for each request where it is sent, and each request is kept in the record when it is sent.

## Impact

- `src/devops_cli/server/service.py`
- `src/devops_cli/github/rate_limiter.py`
- `src/devops_cli/lang/en/messages.py`
- `tests/test_service_limits.py`
- `openspec/specs/roadmap-service-limits/spec.md`

## Feasibility

- **Request path**: `GitHubRateLimiter.acquire` is called once for each `gh` command attempt (`_execute_gh_single_attempt`) and for each request of the session (`session_transport`). It is the point where `devops_cli_github_requests_total` is counted, so the budget and the telemetry count the same requests.
- **Record format**: the old record is a list of `[time, count]` pairs. A request is one pair with count 1, so a record that an older pod wrote still reads.

## Existing Tool Considered

The `limits` package (moving window) was considered. It has no wait that a stop can end and no record that a restart reads back. The Service already has both in `RequestBudget`, so the fix moves the check to the request and adds no dependency.
