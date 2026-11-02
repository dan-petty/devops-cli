# Proposal

## Why

Issue #2919: nothing measures how long an item waits in a roadmap state. Items sat in Ready, in Planned and as stopped drafts for hours or days before a person saw them. The issue asks for a gauge of the age of the oldest item in each state, a gauge of the age of the oldest claim, one alert and one panel.

On 2026-11-02 the open issues had 78 items with a status label. The oldest Ready item with a plan had waited 74 hours (Feasibility 4). No metric, alert or panel showed it.

## What Changes

- `src/devops_cli/telemetry/instruments.py` declares three gauges: `devops_cli_roadmap_item_age_seconds` (the age of the oldest open item), `devops_cli_roadmap_oldest_item_number` (the issue number of that item, as the value) and `devops_cli_roadmap_claim_age_seconds` (the age of the oldest claim). The item gauges carry the labels `repo`, `state` and `plan`. The claim gauge carries `repo`.
- `RoadmapStore` gets `label_changes(number)`: the `labeled` and `unlabeled` events of one issue, oldest first. `GitHubRoadmapStore` reads `repos/<repo>/issues/<number>/events`. `InMemoryRoadmapStore` returns the changes that its writes recorded.
- `src/devops_cli/github/metrics.py` computes the ages. For each open item with a status or an owner label, it takes the time of the `labeled` event that set the current label, and subtracts it from an injectable clock. It keeps the time for each item in the process, so it reads the events of an item again only when the status or owner label of the item changes. `ProjectMetricsReport` gets `item_ages`. `emit_project_metrics_telemetry` sends them through `emit`.
- `_run_metrics_adapter` in `src/devops_cli/roadmap/run.py` asks for the ages. `devops gh metrics` does not, so a run from a workstation reads no events and sends no age.
- `k8s/monitoring/prometheus-values.yaml` gets the group `roadmap-service-items` with one alert, `RoadmapServiceItemStuck`. It fires when an item stays in `blocked`, or in `ready` with a plan, for more than 24 hours. Its summary names the item number. A promtool unit test pins it.
- `k8s/monitoring/dashboards/project-metrics.json` gets the panel "Oldest Item Age by State" in the items row.
- `docs/TELEMETRY.md` (generated) and the runbook in `k8s/README.md` describe the gauges and the alert.
- The change carries a spec delta in `project-metrics-dashboard` and `roadmap-service-alerts`: the metrics, the alert and the panel are observable (`openspec/config.yaml`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: the metrics row sends the age gauges, and the project dashboard shows them
- `roadmap-service-alerts`: one alert fires for a stuck item and names it

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/roadmap/run.py`
- Manifests: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/project-metrics.json`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/conftest.py`, `tests/roadmap_github_fake.py`, `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml` (new)
- Documents: `docs/TELEMETRY.md` (generated), `k8s/README.md`
- Left as they are, on purpose: `project_metrics_requests` (`src/devops_cli/github/metrics.py:678`) is the request plan of `devops gh metrics --dry-run` (`src/devops_cli/commands/gh.py:2172`). That command collects no ages, so its plan does not change. The Service has no request plan for its rows (`src/devops_cli/roadmap/run.py` imports no `request_plan`). `devops roadmap inbox` keeps its own "age", the time since the last update (`src/devops_cli/roadmap/inbox.py`, module docstring): it is a different measure and a person reads it as a list. The existing requirement "A label set that has no items is sent as 0 once" covers `devops_cli_project_items`, an open set of labels. The age gauges have a closed set, so they send every pair each round.
- `devops gh metrics --format json` prints `item_ages` as an empty list. The command sends no new request.

## Dependencies

- #2968 (inbox counts as gauges and an inbox panel, open) edits `src/devops_cli/telemetry/instruments.py`, `k8s/monitoring/dashboards/project-metrics.json` and the metrics row too. The age panel takes `x` 0 to 12 at `y` 34, and leaves `x` 12 to 24 free for the inbox panel, as the owner asked on #2919. Whichever change merges second merges main and regenerates `docs/TELEMETRY.md`.
- #2950 (alternatives coverage gauges and an alert) and #3240 (tool-call telemetry) both add instruments to `INSTRUMENTS` and rows to `docs/TELEMETRY.md`. Both name a "Roadmap dashboard" in their text. No such file exists (`ls k8s/monitoring/dashboards` lists 15 dashboards, none for the roadmap). This change puts its panel in `project-metrics.json`, where the items panels are. The plan of #2950 puts its alert in the group `roadmap-service-activity`. This change adds its own group, so the two changes edit different rule groups, and only the tuple `RULE_GROUP_TESTS` in `tests/prometheus/test_k8s_monitoring_alerting.py` is shared.
- #3069 (dashboards and alerts for the pipeline) leaves the state-age metric and the stuck-item alert to this issue, and the owner called an issue number as a label "unsafe" there (comment of 2026-11-02). This design keeps the issue number out of the labels (design.md).
- #2908 is the parent tracker. #2910 added the `owner/*` claim labels that the claim gauge reads, and it is merged. #2742 asks to bound the values of one label. It does not touch these gauges.
- I searched open issues and pull requests for `2919`, `INSTRUMENTS`, `gauge alert dashboard panel promtool` and `telemetry instruments` on 2026-11-02. No issue says to park or wait for this change.

## Feasibility

Checked on `origin/main` 69234732, on 2026-11-02, with the commands below.

1. The gap is real. `git grep -n -i "roadmap_item_age\|roadmap_claim_age\|oldest_item" -- src tests k8s docs` printed nothing (exit 1). `ls k8s/monitoring/dashboards` lists no roadmap dashboard.
2. GitHub gives the time of a label event per issue. `gh api "repos/dan-petty/devops-cli/issues/2919/events?per_page=100"` printed, among 11 events, `unlabeled 2026-11-01T02:48:06Z status/new` and `labeled 2026-11-01T02:48:06Z status/ready`. The payload has the keys `actor, commit_id, commit_url, created_at, event, id, node_id, performed_via_github_app, url` and a `label` object for label events, and no `issue` key. `_EventPayload` (`src/devops_cli/roadmap/github_store.py:234`) reads `issue.number`, and `change()` returns None without it (`:244-247`), so the per-issue listing needs its own payload class.
3. The repository-wide listing cannot reach old events. `gh api "repos/dan-petty/devops-cli/issues/events?per_page=100&page=300"` printed 100 events from 2026-09-09. Page 301 printed `In order to keep the API fast for everyone, pagination is limited for this resource.` (HTTP 422). An item in a state since before that has no event in this listing.
4. The algorithm works on the real repository. A scratch script (outside the tree) read the 78 open items that hold a status label, one `issues/<n>/events?per_page=100` request each, took the latest `labeled` event of the current label that no `unlabeled` event followed, and printed the oldest item of each pair of a status and a plan flag (a `"stage.pr"` key in the record block of the body): `status/ready` with a plan: item 2754, 74.5 hours; `status/ready` without: item 2713, 71.2 hours; `status/new`: item 2736, 88.2 hours; `status/blocked` with a plan: item 3050, 14.2 hours; `status/planned` with a plan: item 2743, 0.4 hours. It sent 78 requests. The most events on one item was 13, so one page is enough. It found no item with an owner label.
5. The steady cost is small. The repository events of the last 24 hours (18 pages) held 209 `labeled` events of a `status/*` label on open issues, on 70 distinct issues. A read of an item only when its label changes costs at most 209 requests in that day, about 9 an hour. The budget is 500 an hour (`DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR`, `src/devops_cli/config/defaults.py:903`) and the metrics row runs every 13 minutes (`DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES`, `:712`). A read of all 78 items each round would cost 78 x 4.6 = 360 an hour. The first round after a start costs 78 requests, 16% of one hour.
6. The row reads GitHub through the store. `_run_metrics_adapter` passes `store` to `collect_project_metrics_report` (`src/devops_cli/roadmap/run.py:645`), and `tests/roadmap/test_roadmap_run.py:1375` runs the row over `InMemoryRoadmapStore`. A direct `gh` call in the row would run the real program in those tests.
7. A number can be the value of a gauge and still reach the message. I wrote the rule and a unit test in a scratch directory and ran promtool 3.15.1 (the version of `src/devops_cli/tools_lock/tools.lock`, archive sha256 `6a726885...d97a84` matched). The rule's summary used `{{ with printf "max(last_over_time(devops_cli_roadmap_oldest_item_number{...}[30m]))" ... | query }}`. `promtool check rules` printed `SUCCESS: 1 rules found`. `promtool test rules` printed `SUCCESS` for a case that expected `Item #2919 of example/app has been blocked for 1d 1h 0m 0s`, and the same case held a `ready` series with `plan="false"` that did not fire.
8. The alert group has a test pattern. `tests/prometheus/test_k8s_monitoring_alerting.py` holds `RULE_GROUP_TESTS` (`:89`), `SERVED_SERIES` (`:96`), the rule pin `test_the_baseline_rule_set` (`:248`), and `test_each_roadmap_service_alert_points_to_its_step_in_the_readme` (`:1195`). Of the six Service rules with a numeric threshold, five use a literal (`RoadmapServiceLaneStalled` 7200 seconds, `RoadmapServiceModelRequestsHigh` 352, `RoadmapServiceWebhooksRejected` 20, `RoadmapServiceGitHubWritesHigh` 300, `RoadmapServiceSelfDeliveriesHigh` 150). `RoadmapServiceGitHubRequestsHigh` follows `devops_cli_service_budget_limit_requests`. That series needs `service.github_requests_per_hour` (`src/devops_cli/config/settings.py:952`), `src/devops_cli/k8s/configmap.py`, `src/devops_cli/server/service.py:206`, `src/devops_cli/config/constants.py:1543`, `docs/ENV_VARS.md:114` and `docs/CONFIGURATION.md:262`.
9. The ratchet allows a typed catch. `tests/fixtures/swallowed_failures_ceilings.json` holds 4 for `src/devops_cli/github/metrics.py` and 4 for `src/devops_cli/roadmap/run.py`. A catch of `GitHubOperationError` is not a blind `except`, so it adds none.

Not verified: the real run of the new code (this is a plan), and the churn of the number gauge, which I did not measure.

## Existing Tool Considered

Prometheus, Alertmanager and Grafana already cover storage, alert rules and panels, and the change uses them as they are. The need is the age of an item in a label state. promhippie/github_exporter (Apache-2.0) is the open exporter for GitHub metrics. Its source on the default branch declares `github_repo_issues` and `github_admin_issues_open`, `_closed` and `_total` (counts) and no metric by label or by age (`pkg/exporter/repo.go`, `admin.go`, `org.go`). Grafana's data source plugins read the GitHub API but give no alert rule in our Prometheus. So no open tool covers the need, and the change builds it.

Cost to build: about 70,000 tokens (a store method with its payload, the age code and cache, three instruments, a flag in the row, a rule with its unit test, a panel, and tests in six files) and about 5 hours with two CI runs. Cost to keep: about 4,000 tokens each quarter. Cost to fix one miss: about 12,000 tokens. The change reuses `emit`, the store, the session pager and the alert test pattern. It deletes no internal code.
