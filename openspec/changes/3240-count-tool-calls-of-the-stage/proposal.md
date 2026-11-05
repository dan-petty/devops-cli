# Proposal

## Why

Issue #3240: a person who tunes the toolset of the stage planner cannot see which tools a plan run calls. The `RunTrace` comment on an item lists the calls of one run as text. No metric exists, so no trend shows across runs. The alternatives check ran 34 times and searched about 4 times, and nothing showed it (#2950). The same blind spot can hide a tool that the planner never calls. This change counts each tool call by tool and outcome, measures the size of each answer, and warns when a tool of the toolset has no call for 7 days.

## What Changes

- `src/devops_cli/telemetry/instruments.py` declares four instruments: the counters `devops_cli_roadmap_tool_calls_total` and `devops_cli_roadmap_tool_limit_hits_total`, and the histograms `devops_cli_roadmap_tool_answer_chars` and `devops_cli_roadmap_tool_calls_per_run`. The labels are `tool`, `row`, `toolset`, `outcome` and `limit`. The issue names the label `row` as `job`: see Feasibility 3.
- `RunTrace` in `src/devops_cli/roadmap/agent_run.py` records the outcome (`ok`, `empty` or `error`) and the answer size of each tool call, read from the `ToolReturnPart` of the run messages, and the limit that ended the tools of the run.
- `src/devops_cli/roadmap/tool_metrics.py` is new. It sends the zero increments at the start of a run and the counts of a run at its end, through `emit`.
- `ToolboxClient` in `src/devops_cli/roadmap/stage_toolbox.py` calls both functions around each plan run.
- `investigate` in `src/devops_cli/roadmap/refine_investigation.py` names the limit that ends the tools of a run: `calls`, `requests` or `window`.
- `_run_report` in `src/devops_cli/roadmap/stage.py` adds one line to the comment of a staged item: the calls and the empty answers of each tool.
- `k8s/monitoring/dashboards/project-metrics.json` gets one panel, "Planner Tool Calls and Answer Size", next to "Oldest Item Age by State".
- `k8s/monitoring/prometheus-values.yaml` gets the group `roadmap-service-tools` with the alert `RoadmapServiceToolUnused`. A `promtool` unit test covers it. The pins in `tests/prometheus/test_k8s_monitoring_alerting.py` and the section "Roadmap service" of `k8s/README.md` name it.
- `tests/telemetry/test_telemetry_instruments.py` gets a check that no `emit()` call sends the attribute `job` or `instance`.
- `docs/TELEMETRY.md` is generated from `INSTRUMENTS`, and says that the resource sets `job` and `instance`.
- The change has spec deltas: a metric, a comment line, a panel and an alert rule are observable (`openspec/config.yaml`). It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The tool-call instruments are declared and documented, No instrument attribute is named job or instance
- `roadmap-stage`: A plan run counts each tool call by outcome, A plan run measures the size of each answer, Each plan run gives every tool of its toolset a series, A plan run measures its calls and the limit that ended its tools, The comment of a staged item counts the calls of each tool
- `project-metrics-dashboard`: The items dashboard shows the tool calls of the planner
- `roadmap-service-alerts`: The planner tools have their own alert group

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`
- Manifests: `k8s/monitoring/dashboards/project-metrics.json`, `k8s/monitoring/prometheus-values.yaml`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tools_tests.yaml`
- Documents: `docs/TELEMETRY.md` (generated), `k8s/README.md`
- Deleted code: `_within_budget`, `_within_window_of` and `_recording` in `refine_investigation.py`. `_limit_reached` and `_offering` replace them.

## Dependencies

- #3238 (merged) added the toolset `extended` and the label value `toolset`. Nothing to wait for.
- #2919 (merged) put the age panel in `project-metrics.json`. The free right half of its row holds the new panel.
- #2950 (open plan) adds three alternatives instruments, one alert in the group `roadmap-service-activity` and a panel row. Both plans edit `INSTRUMENTS` and `__all__`, the table in `docs/TELEMETRY.md`, `SERVED_SERIES`, the baseline rule list in `tests/prometheus/test_k8s_monitoring_alerting.py` and `k8s/README.md`. The change that merges second merges `main` and keeps both entries. This change adds its alert to a new group, so no requirement is in both plans.
- #3069 (open) may create a dashboard of its own. This change does not wait for it: the panel moves with a one-line edit of the file name.

## Feasibility

Checked on `origin/main` 2db71f29. Each premise has its output.

1. The module declares and sends instruments as the issue says. `git grep -n "ROADMAP_STAGE_TOTAL" src` shows the instrument, its entry in `INSTRUMENTS` and its `emit` in `stage.py`. `git grep -n "devops_cli_roadmap_tool" -- . ':!openspec'` prints nothing: the four names are free. `docs/TELEMETRY.md` is generated by `generate_telemetry_docs` in `src/devops_cli/docs/generator.py` from `INSTRUMENTS`.
2. The issue asks for a panel in "the Roadmap dashboard". `ls k8s/monitoring/dashboards` lists 15 files, and none is a Roadmap dashboard. `project-metrics.json` holds the items panels. Its panel "Oldest Item Age by State" has `gridPos` `{"h": 8, "w": 12, "x": 0, "y": 34}`, so the right half at `x` 12 is free. The panel goes there.
3. The label `job` of the issue cannot work. The OTLP resource sets `service.name` as the Prometheus label `job`. `createAttributes` in `pkg/translator/prometheusremotewrite/helper.go` of opentelemetry-collector-contrib copies the data point attributes into a map first. It then runs `l[model.JobLabel] = val` for `service.name`, with no log. So a data point attribute named `job` is lost, and `job="stage"` would match nothing. The same holds for `instance`. `devops_cli_github_requests_total` names the same idea `row` (`src/devops_cli/github/request_scope.py`). The four instruments use `row` with the value `stage`, and the dashboard and the alert read `row`.
4. A zero increment reaches the collector. A test that called `increment_counter("devops_cli_roadmap_tool_calls_total", 0, attributes={"tool": "read_file"})` on the `otlp` fixture exported one sum data point with `asDouble` 0.0 and delta temporality. So the zero increment at the start of a run gives each tool a series.
5. pydantic-ai 2.59.0 already records each tool answer. `ToolReturnPart` holds `content` (the text that the model reads, after the cut of each tool), `tool_call_id` and `outcome`. A rejected call gives a `RetryPromptPart` with the same `tool_call_id`. `RunTrace.absorb` already reads the same messages. So the counts come from the messages, with no wrapper of the tool functions and no `Hooks` capability. A hook would miss a call that failed in argument validation.
6. The tools answer a failure as text, so an answer with text is `ok` even when it says "No match." The refined design of the issue defines `empty` as an answer with no non-whitespace character. An exception, a rejected call and a call that the run never answered are `error`.
7. The alert expression works in promtool 3.15.1, the version of `src/devops_cli/tools_lock/tools.lock` (`promtool --version`). A scratch rule over two counter series and one native histogram series, with the input `{{schema:0 sum:3 count:1 buckets:[1]}}`, passed `promtool check rules` and `promtool test rules`. The rule fired for the tool whose counter stayed at 0 and stayed quiet for the tool whose counter grew each hour. A first run of the same case, where the called tool had its last call 12 days before, correctly fired for both tools.
8. The limit hooks are in one module. `_within_budget`, `_within_window_of` and `_recording` in `refine_investigation.py` end the tools by `tool_calls_limit` (fewer than `CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS` calls left), by `request_limit` (one request left) or by the context window. Only `refine_investigation.py` reads them. `tests/roadmap/test_roadmap_stage_toolbox.py` already runs the three cases with `Script`.
9. A hard stop by `UsageLimitExceeded` can happen with no earlier cut: one reply with 201 calls does it (`test_one_reply_over_the_call_limit_fails_the_run_and_names_the_limit`). The message of that error is not read. The count of replies of the run against `request_limit` names the limit: `requests` when they are equal, else `calls`.

Not verified: how a real Prometheus stores the zero sample of a new series from a Service pod, and the live values of the new series. No collector or cluster is reachable from this session. The promtool cases feed the label sets that `docs/TELEMETRY.md` describes.

## Existing Tool Considered

pydantic-ai, which the planner already uses, records every tool call and answer in the run messages. `RunTrace` reads them and no new library is needed. The OpenTelemetry SDK, through `emit()`, sends the values. Prometheus, `promtool` and Grafana store, test and show them. The alternatives check of 2026-11-05 found no open tool: agent instrumentation such as OpenLLMetry records tool calls as spans, and gives no `empty` outcome, no answer size after the cut, no calls per run and no limit hits as metrics. So this repository builds the four instruments, the tally and the rule.

Cost to build: about 70,000 tokens and about 4 hours with the CI waits (seven groups, five of them with a failing test first). Cost to keep: about 3,000 tokens each quarter, when the toolset changes. Cost to fix one miss: about 8,000 tokens, with a failing test that names the label. The change deletes the three hook functions that `_limit_reached` and `_offering` replace.
