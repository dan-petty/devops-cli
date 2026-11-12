# Proposal: #4680

## Why

No test runs a query of a Grafana dashboard panel (#4680). The one query test of `tests/prometheus/test_k8s_monitoring_dashboards.py` compares a recorded live answer with the priced series, and does not evaluate the query. So panels with wrong numbers shipped with no failed test: the throttle bars of `devops-cli.json` add up to 474 in 24 h for 21 throttles, and the spend rate of `ai-spend.json` adds up to 43 % of the spend at 7 d. The dashboard items of #4675 need one evaluator that runs a panel query on fixture series.

## What Changes

- A new test module, `tests/prometheus/test_dashboard_queries.py`, reads the cases in `tests/fixtures/dashboard_queries/<dashboard>.yaml`. Each case names the panel title, the target refId, the query, the values of the Grafana variables, the evaluation time and the expected samples.
- The test fails when the query of a case is not the current query of its panel target, and names the dashboard, the panel title and the refId.
- The test replaces the variables as Grafana does: `$__range`, `$__range_s`, `$__range_ms`, `$__interval`, `$__interval_ms` and `$__rate_interval`, from the Min step of the target or the scrape interval of its data source. It writes one promtool unit test file for each dashboard and runs `promtool test rules` once on it. The test skips where promtool is not installed (`@pytest.mark.live("promtool")`).
- The first fixture file, `devops-cli.yaml`, holds the four series shapes of #4675 once each: a counter sent each 15 min, a series that starts with a zero sample, a counter that drops when a pod starts, and a gauge that a snapshot writes each 15 min. Its cases cover panels that are correct today: "AI Spend in Range" and "Alternatives Unchecked Items".
- The promtool run of `tests/prometheus/test_k8s_monitoring_alerting.py` moves to `tests/support/promtool.py`, so the two modules share it.
- `docs/TESTING.md` tells how to add a case.
- The change adds tests, fixtures and a document only. A consumer observes no new behavior, so it has no spec delta (`skip_specs: true`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tests/prometheus/`, `tests/support/` and `tests/fixtures/dashboard_queries/`: a new test module, a shared promtool run and a fixture file.
- `docs/TESTING.md`: a new section, "Dashboard queries".
- The dashboard items #3655, #3851 and the items of #4675 add their cases to this harness, so the repository keeps one evaluator of panel queries.
- CI installs the pinned promtool already (`.github/workflows/ci.yml`, step "Install promtool"), so the new test runs in CI with no workflow change.

## Feasibility

- promtool 3.15.1, the version of `src/devops_cli/tools_lock/tools.lock`, runs a unit test file with no `rule_files` and only `promql_expr_test` cases: a file with the four test groups of `devops-cli.yaml` passes, and a wrong `exp_samples` value fails with exit code 1 and the lines `exp:` and `got:` of the case.
- In promtool, `_xN` gives N empty samples, and `a+bxN` gives N+1 samples (probed with `timestamp(x)`). A range selector holds the samples after its start (Prometheus 3), so `[86400s]` at 48h reads the samples from 24h15m to 48h.
- Grafana documents `$__rate_interval` as max(`$__interval` + scrape interval, 4 x scrape interval), where the scrape interval is the Min step of the query, else the scrape interval of the data source (Grafana documentation, "Prometheus template variables"). The live Prometheus data source has `timeInterval` 60s, the value of `k8s/monitoring/grafana-values.yaml`.
- The live roadmap Service writes `devops_cli_project_items` 21 times in 6 h (a snapshot each 15 to 17 min), and its OTLP gauges, such as `devops_cli_service_budget_spent_requests`, 265 times in 6 h. The alternatives coverage gauges are sent once at the start of each round of the check (`record_coverage`, `src/devops_cli/roadmap/alternatives.py`).
- The promtool run of each fixture file took 1.1 s to 2.3 s on the devcontainer, so the new test adds less than 10 s.

## Existing Tool Considered

- promtool, which the repository pins and CI installs, evaluates the PromQL on the fixture series. The new code only replaces the Grafana variables and writes the promtool file.
- No open tool evaluates a Grafana panel target on fixture series. grafanalib builds dashboards, and the Grafana dashboard linter checks the JSON; neither runs a query.
- Cost of the new code: about 120,000 tokens to build, 3,000 tokens a month to keep, 3 h elapsed.
