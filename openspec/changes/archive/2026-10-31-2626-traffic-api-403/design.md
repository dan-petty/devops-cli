# Design: Handle Traffic API 403 for Integration Tokens

## Context
When collecting repository metrics (`get_repository_traffic_metrics`), four traffic endpoints are queried:
- views (`repos/{repo}/traffic/views`)
- clones (`repos/{repo}/traffic/clones`)
- referrers (`repos/{repo}/traffic/popular/referrers`)
- popular paths (`repos/{repo}/traffic/popular/paths`)

When running under an integration token (GitHub App installation token), each call fails with `Resource not accessible by integration (HTTP 403)`.

## Design Decisions
1. **Error detection**:
   - In `_read_json`, inspect errors raised during `client.api(path)`.
   - Identify whether an error is a refusal by token using `is_gh_refused_by_token(str(err.details.get("stderr", "")))` or matching `"Resource not accessible by integration"` in the error message.
2. **Logging**:
   - For errors matching the integration restriction, do NOT log at WARNING level.
   - In `get_repository_traffic_metrics`, if any/all traffic calls were refused by integration token:
     Log exactly one DEBUG line per repository:
     `logger.debug("Traffic API not accessible by integration for %s: skipping traffic metrics", repo)`
   - For all other errors, preserve `logger.warning("Failed to query %s: %s", what, err)`.
3. **Telemetry emission**:
   - When traffic endpoints are refused by the integration token, return `TrafficSummaryMetric` with `traffic_collected=False`.
   - `emit_project_metrics_telemetry` checks `report.traffic.traffic_collected` before calling `_emit_traffic`. When `traffic_collected` is False, no `PROJECT_TRAFFIC_*` gauges are emitted.
