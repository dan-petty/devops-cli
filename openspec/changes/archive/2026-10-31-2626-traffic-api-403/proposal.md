# Proposal

## Why
Issue #2626: The roadmap Service logs four WARNING lines per repository per metrics cycle when running with a GitHub App integration token:
`Failed to query traffic <endpoint> for <repo>: gh api call failed with exit code 1: gh: Resource not accessible by integration (HTTP 403)`
GitHub returns `Resource not accessible by integration (HTTP 403)` on each traffic endpoint for an integration token because integration tokens lack the repository Administration permission. This restriction is permanent by design.
In addition, `get_repository_traffic_metrics` returns a `TrafficSummaryMetric` with `traffic_collected=True` and zeroes for traffic counts, causing `emit_project_metrics_telemetry` to emit zero-valued `PROJECT_TRAFFIC_*` gauges that misrepresent repository activity.

## What Changes
- Detect `Resource not accessible by integration` on GitHub traffic API calls.
- When the traffic API returns the integration restriction for a repository, log exactly one DEBUG line per repository instead of four WARNING lines.
- Preserve WARNING logs for other traffic API failures (such as HTTP 502, network errors, or rate limits).
- Mark `traffic_collected=False` in `TrafficSummaryMetric` when traffic collection is refused by the integration token, preventing the emission of zero-valued `PROJECT_TRAFFIC_*` gauges.
- Add and update tests in `tests/test_github_metrics.py`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- None.

## Impact
- Source files: `src/devops_cli/github/metrics.py`.
- Test files: `tests/test_github_metrics.py`.

## Feasibility
Confirmed against `src/devops_cli/github/metrics.py`:
- `_read_json` catches exceptions from `client.api(path)` and currently calls `logger.warning("Failed to query %s: %s", what, err)` unconditionally before checking `is_gh_refused_by_token`.
- `get_repository_traffic_metrics` calls the four traffic fetch functions and always sets `TrafficSummaryMetric(views_count=..., ...)` with default `traffic_collected=True`.
- In `emit_project_metrics_telemetry`, traffic metrics are emitted only when `report.traffic.traffic_collected` is true. Setting `traffic_collected=False` when traffic endpoints are refused by the token avoids emitting misleading zero gauges.
