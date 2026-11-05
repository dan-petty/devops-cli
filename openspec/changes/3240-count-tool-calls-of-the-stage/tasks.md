# Tasks

## 1. Declare the four tool-call instruments

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 Add a test to `tests/telemetry/test_telemetry_instruments.py` that finds `devops_cli_roadmap_tool_calls_total` and `devops_cli_roadmap_tool_limit_hits_total` as counters with the unit `1`, `devops_cli_roadmap_tool_answer_chars` as a histogram with the unit `{char}`, and `devops_cli_roadmap_tool_calls_per_run` as a histogram with the unit `{call}`, in `INSTRUMENTS`
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 1.2 Add `ROADMAP_TOOL_CALLS_TOTAL`, `ROADMAP_TOOL_ANSWER_CHARS`, `ROADMAP_TOOL_CALLS_PER_RUN` and `ROADMAP_TOOL_LIMIT_HITS_TOTAL` to `src/devops_cli/telemetry/instruments.py` after `ROADMAP_STAGE_TOTAL`, each with a description in the style of its neighbors. Add the four names to `INSTRUMENTS` and `__all__`
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Keep the labels job and instance out of emit

Reads: `tests/telemetry/test_telemetry_instruments.py`. Changes: `tests/telemetry/test_telemetry_instruments.py`.

- [x] 2.1 Add a check to `tests/telemetry/test_telemetry_instruments.py`, beside `test_every_metric_is_a_declared_instrument_sent_through_emit`, that names each `emit()` call under `src/devops_cli/` whose attribute dict has the key `job` or `instance`. Add a test of the check on a module text: `emit(COMMAND_TOTAL, 1.0, {"job": "stage"})` is named, and `emit(COMMAND_TOTAL, 1.0, {"row": "stage"})` is not
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## 3. Record the outcome, the size and the limit of each tool call in the trace

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/support/scripted_model.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`.

- [x] 3.1 Add tests to `tests/roadmap/test_roadmap_stage_toolbox.py` for the records of `client.traces`: a call with text is `ok` with the length of its answer, a blank answer is `empty`, a call with no `path` is `error`, and a call after the tools were removed is `error`. A tool answer of 300 long lines gives the length of the cut answer that the model read. The run that spends its call budget has the limit `calls`, the run that fills a window of 12000 tokens has `window`, the run that spends its requests has `requests`, one reply over the call limit has `calls`, and a run that stops on no limit has none. `RunTrace.combined` keeps the last limit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/agent_run.py`, add `ToolOutcome` and `RunLimit` as string enums. Add `outcome` and `chars` to `ToolCallRecord` and `limit` to `RunTrace`. Make `RunTrace.absorb` read the answer of each call from the `ToolReturnPart` or the `RetryPromptPart` with the same `tool_call_id`, and take a `limit`. Add `RunTrace.tool_counts`. In `src/devops_cli/roadmap/refine_investigation.py`, replace `_within_budget`, `_within_window_of` and `_recording` with `_limit_reached` and `_offering`, keep the first limit of the run, name the limit of a `UsageLimitExceeded` from the count of replies, and pass it to `trace.absorb`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` passes
- [x] 3.3 Run the other tests of the investigation, which share the hooks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_investigation.py`

## 4. Send the counts of each plan run

Reads: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/telemetry/instruments.py`, `tests/support/fakes/otlp.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`. Changes: `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`.

- [x] 4.1 Add tests with the `otlp` fixture to `tests/roadmap/test_roadmap_stage_toolbox.py`: a run that calls `read_file` with text, a blank tool and `read_file` with no `path` gives one point of the counter for each outcome with the labels `tool`, `row`, `toolset` and `outcome`; a run with the toolset `base` that makes no call gives nine zero points; the histogram of answers holds the cut length; a run that spends its call budget gives one observation of calls per run and one limit point `calls`; a run whose second model request fails counts its first call and observes no calls per run; every label value is in its closed set
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` fails on the base
- [x] 4.2 Add `src/devops_cli/roadmap/tool_metrics.py` with `start_run`, which adds 0 to the counter for each tool of the toolset, and `end_run`, which sends the counter, the answer histogram, the calls per run and the limit of a `RunTrace`. Call them in `ToolboxClient.chat_structured` before and after the run, with `row` `stage` and the toolset of the client
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` passes

## 5. Count the calls of each tool in the comment

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 5.1 Add tests to `tests/roadmap/test_roadmap_stage_apply.py`: the comment of a run with two tools holds `Tool calls: list_files=1 (empty=0), read_file=2 (empty=0)`; the comment of an item with two plan runs sums the counts; the comment of a run with no tool call holds no line `Tool calls:`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [x] 5.2 Add `stage_comment_tool_counts` and `stage_comment_tool_count` to `src/devops_cli/lang/en/messages.py`. In `_run_report` of `src/devops_cli/roadmap/stage.py`, append the line from `RunTrace.tool_counts` after the list of calls
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` passes

## 6. Add the unused-tool alert, its promtool cases and the pins

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml`, `k8s/README.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tools_tests.yaml`, `k8s/README.md`.

- [x] 6.1 Add `tests/fixtures/prometheus_rules/roadmap_service_tools_tests.yaml` with the cases of the spec, with the real label sets (`job="roadmap-service"`, `instance="roadmap-service"`, `row`, `toolset`, `tool` and `outcome`) and a native histogram for the runs. In `tests/prometheus/test_k8s_monitoring_alerting.py`, add the group `roadmap-service-tools` to `ROADMAP_SERVICE_GROUP_TESTS`, `RoadmapServiceToolUnused` to `test_the_baseline_rule_set`, and the two series names to `SERVED_SERIES`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 6.2 Add the group `roadmap-service-tools` with the alert `RoadmapServiceToolUnused` to `k8s/monitoring/prometheus-values.yaml`: `for: 0m`, severity `warning`, the expression of design.md, and a summary and a description that name the tool and the toolset and end with `(k8s/README.md, Roadmap service)`. Add its row to the alert tables of the section "Roadmap service" in `k8s/README.md`, and add the fixture to the list of the unit-test files in that section
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes with promtool 3.15.1 on the PATH

## 7. Add the panel to the devops-cli dashboard

Reads: `k8s/monitoring/dashboards/devops-cli.json`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `k8s/monitoring/dashboards/devops-cli.json`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 7.1 Add a test to `tests/telemetry/test_telemetry_instruments.py`, beside the test of "Oldest Item Age by State", that pins the panel "Planner Tool Calls and Answer Size", its two queries, each with `row="stage"`, and its place
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 7.2 Add the row "Planner Tools" (id 33, `y` 94) and the panel (id 34, `gridPos` `{"h": 8, "w": 24, "x": 0, "y": 95}`) to `k8s/monitoring/dashboards/devops-cli.json`, with a description that says the values are approximate, the datasource of the other panels, and the second axis for the answer size
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 8. Document the instruments

Reads: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`. Changes: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`.

- [x] 8.1 In `generate_telemetry_docs` of `src/devops_cli/docs/generator.py`, say that an attribute named `job` or `instance` is lost because the resource sets both labels. Run `uv run devops docs generate --sync-readme` to write the four instruments and the sentence to `docs/TELEMETRY.md`
  - Verification: `uv run devops ci docs` passes
- [ ] 8.2 Run the whole gate
  - Verification: `uv run devops ci` passes

## Criteria

- The four instruments are declared, no label has an unbounded value, and `docs/TELEMETRY.md` lists them.: groups 1 and 8
- A test shows one call of each outcome and checks the labels.: group 4
- The trace comment shows the counts for each tool.: group 5
- The alert rule and its unit test pass.: group 6
- `uv run devops ci` passes.: group 8

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
