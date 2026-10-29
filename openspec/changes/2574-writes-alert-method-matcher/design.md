# Design

## The matcher

The rule selects `devops_cli_github_requests_total{job="roadmap-service", method=~"POST|PUT|PATCH|DELETE", resource!="graphql"}`. Prometheus anchors a regular expression at both ends, so the matcher selects exactly the four write methods. The empty string does not match it, so a series with no `method` label is not selected. `resource!="graphql"` stays: `GitHubRateLimiter.acquire` gives each request a `resource` label, so this negative matcher keeps out only the GraphQL requests.

The four methods are the set `CONST_GH_MUTATION_HTTP_METHODS` that `is_write_request` reads. A test holds the matcher of the rule to that set, so a new write method in the classifier fails the test until the rule names it too.

## Rejected alternatives

- **`method!="GET", method!=""`.** Rejected: it keeps a series with no label out, but it still counts each method that is not a GET as a write. `gh api -X HEAD` sends a HEAD, and the classifier calls it a read. The rule must count what the classifier calls a write, and a positive set says that directly.
- **A default `method` label in the pipeline, for example a relabel rule in the collector that sets `method="unknown"`.** Rejected: it changes every series of the counter for one rule, and a negative matcher still counts the default value as a write.

## Tests

- `test_the_roadmap_service_activity_rules_watch_writes_own_deliveries_and_web_search` pins the new expression with the helper `_window_count`.
- `test_the_write_rule_names_each_write_method_of_the_request_classifier` holds each method matcher of the rule to `CONST_GH_MUTATION_HTTP_METHODS`.
- `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` adds the promtool case of a series with no `method` label and 360 requests in an hour, which stays quiet.
