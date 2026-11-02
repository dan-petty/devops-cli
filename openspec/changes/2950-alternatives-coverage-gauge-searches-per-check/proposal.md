# Proposal

## Why

Issue #2950: the alternatives check ran about 34 times in 14 days and searched about 4 times, and no metric, alert or panel showed it. The owner saw it in the Firecrawl usage. #2946 (merged) now makes the check search before a verdict, but nothing proves that it does. This change makes the coverage and the search activity of the check visible: how many open items have no check, how old the oldest check is, how many searches each written check ran, and an alert for three days with no search.

## What Changes

- Declare the gauges `devops_cli_roadmap_alternatives_unchecked_items` and `devops_cli_roadmap_alternatives_oldest_check_age_seconds`, and the histogram `devops_cli_roadmap_alternatives_searches`, in `src/devops_cli/telemetry/instruments.py`.
- `select_items` in `src/devops_cli/roadmap/alternatives.py` returns a `Coverage` of the eligible items it reads. `plan_alternatives` puts it in the plan. A new `record_coverage` emits the two gauges with the attribute `repo`. The Service row calls it after the plan, also when the plan has nothing to write.
- `apply_alternatives` observes the histogram once for each check it writes, with the attribute `verdict` and the number of searches of the check, next to the existing `emit(ROADMAP_ALTERNATIVES_TOTAL, ...)`.
- Add the alert `RoadmapServiceAlternativesNotSearching` to the group `roadmap-service-activity` in `k8s/monitoring/prometheus-values.yaml`, with promtool unit tests, the pins in `tests/prometheus/test_k8s_monitoring_alerting.py`, and a row in the alert table of `k8s/README.md`.
- Add the row "Alternatives Check" with three panels to `k8s/monitoring/dashboards/devops-cli.json`. No dashboard has the title Roadmap (see Feasibility), so the row goes into the dashboard that shows the Service's GitHub requests.
- Document the instruments (`docs/TELEMETRY.md` is generated from `INSTRUMENTS`) and the row in `k8s/README.md`.
- The change has a spec delta: a metric, an alert rule and a panel are observable (`openspec/config.yaml`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: Alternatives coverage instruments are declared, The devops-cli dashboard shows the alternatives check
- `roadmap-alternatives`: A round records the coverage of the check, Each written check observes its searches
- `roadmap-service-alerts`: The Service's activity has its own alert group (MODIFIED), No alternatives search with unchecked items warns

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`
- Manifests: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/devops-cli.json`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`
- Documents: `docs/TELEMETRY.md` (generated), `k8s/README.md`
- Left as they are, on purpose: `devops roadmap alternatives` in `src/devops_cli/commands/roadmap.py` (it records no gauge, see design), `docs/ROADMAP_WORKFLOW.md` (it does not describe the metrics of the check), the stale path `tests/test_telemetry_instruments.py` in `src/devops_cli/telemetry/instruments.py` and in `src/devops_cli/docs/generator.py` (the file is `tests/telemetry/test_telemetry_instruments.py`; another change can fix both comments).

## Dependencies

- #2946 (closed, merged in #3127) gave the check its skip classes and the rule that a non-skip item searches before a verdict. It is in the tree (`src/devops_cli/roadmap/alternatives.py:557`, `skip_class_of`). Nothing to wait for. The new instruments measure its result.
- #3171 (open plan of #2919) adds age gauges, one alert and a panel. Its names are different (`devops_cli_roadmap_item_age_seconds`, `devops_cli_roadmap_claim_age_seconds`) and it adds requirements only, so no requirement is in both plans. Both plans edit `INSTRUMENTS` and `__all__` in `instruments.py`, the table in `docs/TELEMETRY.md`, the rule list in `tests/prometheus/test_k8s_monitoring_alerting.py` and `k8s/README.md`. The change that merges second merges `main` and keeps both entries. Its panel goes in `project-metrics.json`, and this change uses `devops-cli.json`, so the two dashboard files do not collide.
- #3174 (open plan of #2947) changes the first-pass limit of `select_items`. Its spec delta is a placeholder today. `select_items` is the function this change extends: read the merged result of #2947 before the implement step, and keep `Coverage` outside the `limit` logic.
- #3069 (open) may create a dashboard `roadmap-pipeline`. #3240 and #2968 also ask for "the Roadmap dashboard", which does not exist. This change does not wait: its row moves with a one-line edit of the file name if a Roadmap dashboard exists first.
- #3243 (open) would add `search_web` to the stage planner. A planner search adds to `devops_cli_firecrawl_searches_total` like a refine search does, so the alert counts it. The row panel "Alternatives Searches per Check" shows the searches of the check alone.
- #2944 (open) adds the queries to the comment of a check. It reads `Check.queries`, as this change does, and writes no metric. #2951 (open) needs a verdict before Ready. Neither edits the code of this change.

## Feasibility

Checked on `origin/main` 4571d5f3 (the merge base of this branch). Each premise has its output.

- The module declares and sends instruments as the issue says. `git grep -n "class InstrumentKind" -A4 src/devops_cli/telemetry/instruments.py` shows `COUNTER`, `GAUGE`, `HISTOGRAM`. `ROADMAP_ALTERNATIVES_TOTAL` is at `instruments.py:243`, and `emit` at `:491` calls `record_gauge` for a gauge and `record_histogram` for a histogram. `git grep -n "alternatives_unchecked\|alternatives_oldest\|alternatives_searches" -- . ':!openspec/changes'` printed nothing: the names are free.
- The job records one metric today. `alternatives.py:905` is `emit(ROADMAP_ALTERNATIVES_TOTAL, 1, {"verdict": check.verdict.value})`, in `apply_alternatives`, after `store.comment(...)`. `grep -rn "emit(" src/devops_cli/roadmap/*.py` shows no other emit in the check.
- The search count is observable. `AlternativesTools.search_web` appends the query to `self.queries` before it calls Firecrawl (`alternatives.py:259`), so a refused search counts. `validate_reply` copies the list with `queries=_clean(tools.queries, allowed)` (`:767`), and `_clean` keeps one text for each text. So `len(check.queries)` is the number of searches that the tools ran. `_skip_check` sets `queries=()` (`:741`): a skip-class check runs no search and has the count 0. `_refusal` refuses the verdict `not-applicable` from the model (`:573-579`), so only a skip-class check has that verdict.
- The gauge values are not in the plan today. `select_items` (`alternatives.py:497-527`) builds `unchecked`, `due` and `current`, skips an item in the retry delay with `continue` before it reads the check time (`:516`), and returns `ordered[:limit]` and `current`. The count and the oldest check need the whole eligible set, so `Selection` needs a new field. For `--item N` the function returns at `:509` without a scan.
- The row cannot record the gauges after `apply_alternatives`. The adapter at `run.py:608-621` calls `apply_alternatives` only `if plan.has_writes`, and a round with no item to check has no writes. `plan_alternatives` returns `AlternativesPlan(repo=repo, off_reason=...)` at once when the check is off (`alternatives.py:846-847`).
- The Firecrawl counter has a different label set from the gauge. `sed -n 843,848p k8s/monitoring/prometheus-values.yaml` gives `devops_cli_firecrawl_searches_total{job="roadmap-service", result=~"402|429"}` in `RoadmapServiceFirecrawlRefused`. The counter has the label `result` (`common_tools.py:48,72`: `ok`, a status, or `error`). The new gauge has `repo`. Refine searches through the same function (`refine_investigation.py:268` calls `cited_web_search`, which calls `firecrawl_search`), so the counter holds the searches of every job.
- The alert expression of the issue does not fire. I downloaded promtool 3.15.1 (the version of `src/devops_cli/tools_lock/tools.lock`, SHA-256 `6a726885...d97a84` matches) and ran a unit test with the real label sets. Series: `devops_cli_firecrawl_searches_total{job="roadmap-service", instance="roadmap-service", result="402"}` flat at 2, and `devops_cli_roadmap_alternatives_unchecked_items{job="roadmap-service", instance="roadmap-service", repo="example/app"}` at 2, for 150 hours. The rule `increase(devops_cli_firecrawl_searches_total{job="roadmap-service"}[3d]) == 0 and devops_cli_roadmap_alternatives_unchecked_items{job="roadmap-service"} > 0` gave no alert, because `and` needs equal label sets. The rule of design.md (`sum by (repo) (last_over_time(<gauge>[7d])) > 0 and on() (sum(<count of searches in 3d>) or vector(0)) == 0`) fired with `repo="example/app"`.
- The six cases of the fixed rule pass in promtool 3.15.1 (`promtool test rules unit.yaml` printed `SUCCESS`, `promtool check rules` printed `SUCCESS: 2 rules found`): a flat `402` series and no `ok` search fires; an `ok` search one day before is quiet; no search series at all fires; a gauge of 0 is quiet; a new `ok` series that starts 10 hours before and holds 3 searches is quiet; a search of `job="devops-cli"` does not count, and a gauge sample 100 hours old still fires while one 180 hours old does not. The same new-series case with plain `sum(increase(...[3d])) or vector(0)` fired (`got: Labels:{alertname="Incr", repo="example/app", severity="warning"}`), so the rule needs the form of `_window_count` (#2505).
- The repository tests accept the shapes. `tests/prometheus/test_k8s_monitoring_alerting.py` pins the rule list of the group (`ROADMAP_SERVICE_ACTIVITY_RULES`, `:903`), the whole alert list (`test_the_baseline_rule_set`, `:248`) and `SERVED_SERIES` (`:96`), which has `FIRECRAWL_SEARCHES_TOTAL.name` and none of the new gauges. It also needs each `devops_cli_` selector of the group to have `job="roadmap-service"`, a `for`, a severity, and `(k8s/README.md, Roadmap service)` in the description, with the alert name in that section. Group 5 does each. `promtool` is not on this session's PATH, so these tests skip the live part here; CI installs it.
- The dashboard has no Roadmap dashboard. `ls k8s/monitoring/dashboards` lists 15 files. `grep -il roadmap k8s/monitoring/dashboards/*` finds `ai-spend.json` (a panel of gateway callers) and `project-metrics.json` (items and traffic). `devops-cli.json` is titled `devops-cli Telemetry` (uid `devops-cli-telemetry`) and has six rows, among them "Sub-commands", "RAG Retrieval" and "GitHub API"; its last panel has `gridPos.y` 86 and `h` 8. `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` printed `49 passed` on the base: its dashboard checks (a query names a sent series, a gauge is read through `last_over_time`, a histogram through `rate`, `increase` or `last_over_time`) run over `devops-cli.json` and will cover the new row once the instruments exist.
- A gauge needs the window in the alert. `docs/TELEMETRY.md` says: "Prometheus finds a plain selector only within five minutes of a sample". The row runs every 719 minutes (`DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES`), so the alert reads the gauge through `last_over_time(...[7d])`.
- Not verified: how a real Prometheus stores the OTLP gauge of a Service pod after a restart, and the value of the live gauges. No collector or cluster is reachable from this session. The promtool cases feed the label sets that `docs/TELEMETRY.md` describes (`job` and `instance` from the resource, the attributes as labels).

## Existing Tool Considered

Prometheus, promtool and Grafana cover the need, and the project already uses them for each metric (`docs/TELEMETRY.md`, `k8s/monitoring/prometheus-values.yaml`). OpenTelemetry's SDK, through `emit()`, sends the values. The usage page of Firecrawl shows the total searches of the account, but it cannot join them with the count of unchecked items by repository, and it sends no alert. No open tool counts the items that have no alternatives check, so the Service computes that number. The change builds only three instrument declarations, one function, one rule and one dashboard row. Cost: to build, about 90,000 tokens and 5 hours of elapsed time with the CI waits (seven groups, three of them with a failing test first); to keep, about 4,000 tokens each time the check changes its selection, because `Coverage` follows `select_items`; to fix, one failing test that names the instrument, about 8,000 tokens. The change deletes no internal code.
