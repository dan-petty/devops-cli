# Proposal

## Why

The move of the row work into `roadmap-<row>` pods changes the job of their series, so each alert, dashboard panel and start page widget that reads a raw `job="roadmap-service"` selector breaks one by one; the product rule file holds 32 such lines and no recording rule shares one series with them (#4562).

## What Changes

- Add the group `roadmap-service-recording` to `serverFiles.devops_cli_alerting_rules.yml` of `k8s/devops/monitoring/prometheus-rules-values.yaml`, with the rules `repo_lane_row:devops_cli_service_jobs_total:increase1h`, `service:devops_cli_service_budget_requests_per_limit:ratio` and `repo_row_class:devops_cli_service_job_suspended:max`, each selecting `job=~"roadmap-service|roadmap-.+"`.
- Add `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml` with a `promql_expr_test` case for each recording rule, and add the group to `RULE_GROUP_TESTS` with its case file.
- Add the three record names and `CONST_SERVICE_METRIC_BUDGET_SPENT` to `SERVED_SERIES`, make the two promtool checks read `rule.get("alert")`, and add the checks of the rule name form and of the covered selectors.
- Change `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceRowSuspended` to read the recorded series, and change their cases in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` to supply those series.
- Add a check that each of the three row work alerts reads a recorded series of `roadmap-service-recording` and no raw `job="roadmap-service"` selector.
- Name the group and its three recorded series in the `## Alerting` section of `k8s/README.md` and in the Alerts section of `docs/CLUSTER.md`, and change the rows of the three alerts there.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `product-monitoring-content`: The shared row work series have a recording group, A recording rule name has three parts, A recording rule is not an alert, The monitoring tests count each recorded series as served, The recording cases stay within the rounds bound, The product alert rules have their own values file
- `roadmap-service-alerts`: A row that stays suspended warns, Failed jobs and a stalled lane warn, A high request volume warns

## Impact

- Code: `k8s/devops/monitoring/prometheus-rules-values.yaml`
- Documents: `k8s/README.md`, `docs/CLUSTER.md`
- Tests: `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`

## Feasibility

- The probes confirm the two files of the change: "The path `k8s/devops/monitoring/prometheus-rules-values.yaml` is a file of the staging commit." and "The path `k8s/monitoring/prometheus-values.yaml` is a file of the staging commit." They also say "The path `serverFiles.recording_rules.yml` is no file of the staging commit. No commit in the history deleted or renamed it.", so the group the issue asks for is new.
- The body's file and count do not hold. The `references` tool counts 32 lines with `job="roadmap-service"` in `k8s/devops/monitoring/prometheus-rules-values.yaml` (its first lines are 18, 37, 60, 62 and 75), and the environment values file is `k8s/monitoring/prometheus-values.yaml`. The product file holds those 32 lines, not the 41 of the body.
- No recording rule exists today: `search_code` for `record:` finds only the prose line `docs/CLI_REFERENCE.md:331:the state of the stop from the job record: the class`, and the group at `k8s/devops/monitoring/prometheus-rules-values.yaml:31:- name: roadmap-service` holds `alert` rules only.
- The three covered selectors are `k8s/devops/monitoring/prometheus-rules-values.yaml:60:sum by (repo, lane, row) (increase(devops_cli_service_jobs_total`, `k8s/devops/monitoring/prometheus-rules-values.yaml:139:- alert: RoadmapServiceGitHubRequestsHigh` and `k8s/devops/monitoring/prometheus-rules-values.yaml:200:- alert: RoadmapServiceRowSuspended`; the failed jobs window is 1 hour, so the body's 24 hours is 1 hour.
- The router keeps the job: `k8s/devops/monitoring/prometheus-rules-values.yaml:37:devops_cli_service_identity_refused_total` selects `job="roadmap-service"` and no row pod sends that counter, so its line stays unchanged.
- The staged values of the constants the plan relies on: `src/devops_cli/config/constants.py:1772:CONST_SERVICE_METRIC_JOBS: Final[str] = "devops_cli_service_jobs_total"`, `src/devops_cli/config/constants.py:1790:CONST_SERVICE_METRIC_BUDGET_LIMIT: Final[str] = "devops_cli_service_budget_limit_requests"`, `src/devops_cli/config/constants.py:1791:CONST_SERVICE_METRIC_BUDGET_SPENT: Final[str] = "devops_cli_service_budget_spent_requests"`, `src/devops_cli/config/constants.py:1795:CONST_SERVICE_METRIC_JOB_SUSPENDED: Final[str] = "devops_cli_service_job_suspended"` and `tests/prometheus/test_k8s_monitoring_alerting.py:149:MAX_PROMTOOL_ROUNDS = 1_000`.
- The two sides of the budget do not share a label set: `k8s/devops/monitoring/prometheus-rules-values.yaml:133:so their instance labels differ and on() joins the two sums`. The recording rule sums each side, so the recorded ratio needs no join, and the dashboard already divides two sums at `k8s/devops/dashboards/devops-cli.json:322:max(last_over_time(devops_cli_service_budget_spent_requests{job=~`.
- The gauge that the budget counts is `docs/CLUSTER.md:51:the GitHub requests of the last hour, not counting the answers with status 304`, so the recorded ratio replaces the raw counters with no loss.
- The wiring the plan extends: `tests/prometheus/test_k8s_monitoring_alerting.py:134:RULE_GROUP_TESTS = (`, `tests/prometheus/test_k8s_monitoring_alerting.py:152:SERVED_SERIES = frozenset(`, and the two checks that read `rule["alert"]` over every rule are `tests/prometheus/test_k8s_monitoring_alerting.py:462:assert sorted(tested) == sorted(rule["alert"] for rule in _group(group))` and `tests/prometheus/test_k8s_monitoring_alerting.py:510:sorted(_tested_alerts(rule_tests) - {rule["alert"] for rule in _group(group)}),`.
- `_map_test_tree_path` selects a test only for a test module and for a `.py` file, at `src/devops_cli/commands/ci.py:1907:if path.endswith(CONST_PYTHON_FILE_SUFFIX):`, so `uv run devops ci test tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` runs no test and exits 0. Each group of this plan verifies with `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`, a path that the group changes.
- The recording group, its case file and its test wiring land in one group, and the group of the alerts lands after it. `_group` fails on a name that no rule file holds, at `tests/prometheus/test_k8s_monitoring_alerting.py:339:(rules,) = [group["rules"] for group in _groups() if group["name"] == name]`, so a step that wired the group before the rule file held it would fail its own check.
- The two documents the docs group edits: `docs/CLUSTER.md:143:The rule group` and `k8s/README.md:680:Alertmanager runs from the prometheus chart`, which holds the paragraph on the product rule file; the case files are listed at `docs/CLUSTER.md:187:`tests/prometheus/test_k8s_monitoring_alerting.py` runs the promtool`.
- The plan calls no function whose arguments need a checkout, a client or a network. `uv run devops ci test` and `uv run devops ci docs` each need a checkout of the repository and no network.
- The plan introduces no program: `promtool` is a runner tool of the image, and the tests reach it through `tests/support/promtool.py`. A failing promtool case or test is the failure class `test` (action `repair`), a case over the step budget is `timeout` (action `retry`), and a docs failure is `lint` (action `repair`). The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`, and the tests write only under pytest's `tmp_path`.
- The first checks against the real system: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`, which runs `promtool check rules` over every rule file that `serverFiles` names and `promtool test rules` over each case file of `RULE_GROUP_TESTS`, and `uv run devops ci --check --only k8s`, which renders each Application of the tree once.
- The overlap: pull request #6945 changes `k8s/README.md`, and this change edits the `## Alerting` section of that file at `k8s/README.md:680:Alertmanager runs from the prometheus chart`, so the two edits touch different text and no order is needed.
- The follow-up: #4606 holds the pending work selectors, so this change records no pending work series and adds no rule for them.
- Each modified requirement keeps its name and every one of its scenarios, 1 for the product values file, 4 for the suspended row, 6 for the failed jobs and 9 for the high request volume, and each scenario name is the name of a base scenario, so no new behavior test is needed for them.
- The requirement texts are within the 500-character bound: the added requirement on the recording group is about 290 characters, the modified product values file requirement about 360, and the modified failed jobs requirement about 465, with the alert names, the ratio division and the new pod's 2 hours in its scenarios.

## Existing Tool Considered

Prometheus recording rules and promtool (prometheus/prometheus, Apache-2.0, maintained, last activity 2026-11-18) are in use: the chart loads rule groups from `serverFiles`, and the pinned promtool runs `promtool check rules` and `promtool test rules`. The project-specific part, the three rules and their case files, is written by hand at about 150,000 tokens and 2 hours, and about 3,000 tokens a month to keep. The change builds no tool and deletes no internal code.

## Dependencies

- Pull request #6945 changed `k8s/README.md`, the file this change edits in its `## Alerting` section; it is merged, and the two edits touch different text.
