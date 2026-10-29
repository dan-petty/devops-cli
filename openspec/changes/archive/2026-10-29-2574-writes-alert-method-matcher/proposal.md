# Proposal

## Why

Issue #2574: `RoadmapServiceGitHubWritesHigh` (group `roadmap-service-activity`, #2475) selects the writes with the negative matcher `method!="GET"`. PromQL reads an absent label as the empty string, so this matcher also selects a series with no `method` label, and each request of that series counts as a write. On 2026-10-29 at 00:28 UTC the rule fired at 341 on reads. The pod ran an image from before the `method` label, so no series of the pod had the label. Any other source of the counter without the label, such as a cluster Job from an older image, gives the same false alert.

## What Changes

- `RoadmapServiceGitHubWritesHigh` in `k8s/monitoring/prometheus-values.yaml` selects the writes with the positive matcher `method=~"POST|PUT|PATCH|DELETE"`. It keeps `resource!="graphql"`, because GraphQL sends a read as a POST. A series with no `method` label counts nothing. The comment of the group says why the rule names each write method.
- `k8s/README.md`, "Roadmap service", "Alerts": the row of `RoadmapServiceGitHubWritesHigh` names the write methods, says that a series with no `method` label does not count, and its query uses the selector of the rule.
- `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` gets a promtool case: a series with no `method` label and 360 requests in an hour stays quiet. `tests/test_k8s_monitoring_alerting.py` pins the new expression, and a test holds the method set of the rule to the write methods of the request classifier.
- The change alters a manifest, so it carries a spec delta. It modifies the requirement "A burst of writes or of own deliveries warns" of the capability `roadmap-service-alerts`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-alerts`: the write rule counts only the requests whose method is a write, and a request with no `method` label counts nothing.

## Impact

- Manifest: `k8s/monitoring/prometheus-values.yaml`. Argo CD's `prometheus` Application applies it after the merge.
- Documentation: `k8s/README.md`.
- Tests: `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`.
- No code changes. The counter `devops_cli_github_requests_total` keeps its labels.

## Feasibility

Checked on 2026-10-29 at `origin/main` ef6e0285, with promtool 3.15.0, the version of the Prometheus server of the cluster.

- **PromQL semantics.** The Prometheus documentation ("Querying basics", "Time series selectors") says that a matcher that matches the empty string also selects each series without the label. `method!="GET"` matches the empty string.
- **The defect.** `promtool test rules` over the rule at `origin/main` fires `RoadmapServiceGitHubWritesHigh` with the summary "360 GitHub writes" for one series `devops_cli_github_requests_total{job="roadmap-service", resource="core"}` that has no `method` label and grows by 6 each minute.
- **The method values that the code sends.** `GitHubRateLimiter.acquire` (`src/devops_cli/github/rate_limiter.py`) puts the `method` of its caller on the counter. The GitHub session gives `method.upper()` (`pace_request` in `src/devops_cli/github/session_transport.py`). `run_gh` gives `gh_request_method`: the method of a `gh api` argv, which `parse_gh_api_args` makes upper case, or else `POST` for a write and `GET` for a read. `is_write_request` (`src/devops_cli/github/request_classifier.py`) calls a REST request a write when its method is in `CONST_GH_MUTATION_HTTP_METHODS`: `POST`, `PUT`, `PATCH` and `DELETE`. So the label is an upper-case HTTP method, and the four methods cover each write that the code can send.
- **The live series.** A read-only query of the cluster's Prometheus server through the Grafana MCP tools, `count by (method, resource) (last_over_time(devops_cli_github_requests_total{job="roadmap-service"}[1d]))`, gives the methods `GET`, `PATCH` and `POST`, and one `core` series and one `graphql` series with no `method` label.

## Existing Tool Considered

promtool tests the rule, as for #2475. PromQL's regular-expression matcher is the tool that selects a fixed set of label values. The change builds no tool and deletes the negative matcher.
