# Proposal

## Why

The savings panels count token series from before the `local` and `operation` labels (#2202): a series without `local` counts as local when the gateway served it, and a series without `operation` counts as chat. The last such sample leaves Prometheus' 30-day retention at about 2026-11-23, so the mapping is dead code in 8 queries, in one record and in their tests, and it hides which series the panels really read.

## What Changes

- The 8 savings queries of `k8s/devops/dashboards/ai-spend.json` select `local="true"` only, sum each operation branch by operation and type, and hold no `local=""` selector and no `provider="gateway", server!="cache"` fallback.
- The `label_replace` that maps an absent `operation` label to `chat` goes from each of the 8 queries.
- The descriptions of the three savings panels drop the sentence that a series from before the labels counts as local or as chat.
- `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml` holds one record of the current label set, drops the 21-day record, and drops the key of the deleted price rule.
- `tests/prometheus/test_k8s_monitoring_dashboards.py` fails when a savings query keeps a `local=""` or `provider="gateway", server!="cache"` fallback, names only the `local="true"` selectors, and `_is_local` and `_priced_total` read the labels with no fallback.
- `k8s/README.md` and the telemetry paragraph of `src/devops_cli/docs/generator.py` drop the fallback text, and `docs/TELEMETRY.md` is regenerated from the generator.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: The savings queries price the labelled local tokens at the reference price

## Impact

- Code: `k8s/devops/dashboards/ai-spend.json`, `src/devops_cli/docs/generator.py`
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`
- Tests: `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`

## Feasibility

- The issue cites `k8s/monitoring/dashboards/ai-spend.json`, and the probes answer, word for word: The path `k8s/monitoring/dashboards/ai-spend.json` is no file at the root of the staging commit. and Commit f31dc561 2026-11-12 refactor(k8s): split the product dashboards and rules in place (#5309) deleted or renamed it. The same answer names the candidate, and the probes answer, word for word: The path `k8s/devops/dashboards/ai-spend.json` is a file of the staging commit. The plan uses that path, and no code compensates for the old one.
- The probes answer for the other cited paths, word for word: The path `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml` is a file of the staging commit. and The path `k8s/README.md` is a file of the staging commit. and The path `src/devops_cli/docs/generator.py` is a file of the staging commit. and The path `docs/TELEMETRY.md` is a file of the staging commit.
- The premise holds at the staging commit: `search_code` for `server!="cache", operation` returned exactly 8 lines of `k8s/devops/dashboards/ai-spend.json`, at lines 145, 349, 408, 467, 660, 669, 716 and 725, so the set of 8 savings queries has no member outside those lines and all 8 change in group 1.
- The count of 8 is the test's own assertion: `tests/prometheus/test_k8s_monitoring_dashboards.py:443:` `) == (8, [], [])` from `test_each_savings_query_prices_all_local_tokens_at_the_dashboards_prices`, over the queries that `tests/prometheus/test_k8s_monitoring_dashboards.py:def _savings_targets` returns.
- The staged constants that the plan relies on: `tests/prometheus/test_k8s_monitoring_dashboards.py:83:` `PRICE_VARIABLE = "reference_price_usd_per_token"`; `tests/prometheus/test_k8s_monitoring_dashboards.py:96:` `for local in ('local="true"', 'local="", provider="gateway", server!="cache"')`; `tests/prometheus/test_k8s_monitoring_dashboards.py:98:` `SAVINGS_RECORD = FIXTURES / "recorded_queries" / "ai_spend_local_savings.yaml"`; `tests/prometheus/test_k8s_monitoring_dashboards.py:99:` `SAVINGS_IN_RANGE = "Local Cloud Savings in Range"`.
- The staged guard that group 1 extends: `tests/prometheus/test_k8s_monitoring_dashboards.py:def _misses_a_local_token_or_the_price` checks the two local selectors, the price join and the token counter, and its only assertion about the fallback is `tests/prometheus/test_k8s_monitoring_dashboards.py:424:` `or '"operation", "chat", "", ""' not in expr`. Group 1 replaces that clause with the absence of `local=""` and `provider="gateway", server!="cache"`, so the test fails on all 8 queries until each one drops the fallback and the second acceptance criterion is guarded.
- The annotation-limit test that the security section names: `tests/prometheus/test_k8s_monitoring_dashboards.py:def test_each_configmap_fits_kubectls_last_applied_annotation` asserts that no generated ConfigMap reaches `tests/prometheus/test_k8s_monitoring_dashboards.py:79:` `LAST_APPLIED_ANNOTATION_LIMIT_BYTES = 262_144`.
- The fallback text is at the staged commit in `k8s/README.md:350:` `Remove that mapping when`, in `src/devops_cli/docs/generator.py:1068:` `label that the gateway served counts as local, and a series`, in `docs/TELEMETRY.md:210:` `counts as local, and a series`, and in the three dashboard descriptions that `search_code` for `before the operation label` returned at lines 95, 625 and 680.
- The record and the test hold the old label sets: `search_code` for `deleted_price_rule_first_sample` returned `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml:24:` `deleted_price_rule_first_sample: "2026-10-24T05:21:33Z"` and `tests/prometheus/test_k8s_monitoring_dashboards.py:513:` `first_price = datetime.fromisoformat(saved["deleted_price_rule_first_sample"])`; the record of the 21-day range has series with no `local` label.
- The removal condition is not checked: no tool of this run reads Prometheus, so `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is `not checked`. The first check of the implementation is a person's run of `uv run devops prometheus query 'count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))'` against the cluster Prometheus, after 2026-11-23.
- `uv run devops prometheus query` needs a network to the cluster Prometheus and a client of the Prometheus HTTP API; no runner has either, so a person runs it and records the date and the empty output, and the change starts only after it returns no series.
- The checks the implementation runs are `uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` and `uv run devops docs check`; both run from the runner image, whose tools include `uv`, `devops` and `pytest`, so no program is `NOT_IN_RUNNER`, and the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL` hold, so a step writes only the workspace.
- `references` for `local=""` lists 5 files: `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `k8s/README.md`, and two under `openspec/changes/archive/`; the first three change in groups 1 and 3.
- `references` for `server!="cache"` lists `openspec/specs/gateway-caller-telemetry/spec.md` at line 49, `tests/prometheus/test_k8s_monitoring_dashboards.py` at lines 96 and 550, and two archive files; the test module changes in group 1, and a decision says why the spec stays.
- `find_issues` lists open #5784 and #5932 on the same savings queries and open #5931, whose body says it replaces them; `dependencies` names each with its shared path.
- The issue's own reference `#2194` is closed and `read_issue` reports `No merged pull request closed it`, so the fallback that item added is still in the tree and this change is the one that removes it.
- The plan changes no code that a behavior test could drive, so group 1 is a `manifest` group: its `verify` runs `tests/prometheus/test_k8s_monitoring_dashboards.py`, the module that checks the dashboard and the record, and each scenario of the delta names a command (`uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py`) rather than a function, which `src/devops_cli/roadmap/stage/stage_change.py:def _is_scenario_command` exempts.
- No scenario of the delta names a function or a file of the code in a code span: `local="true"`, `operation`, `expr` and `result` hold no dot and no underscore, so `src/devops_cli/roadmap/stage/stage_change.py:def _is_code_identifier` judges no span of them and no behavior test is needed for a span.

## Existing Tool Considered

No open, maintained tool covers the need: `grafana/dashboards-linter` lints Grafana dashboards and cannot remove a dead PromQL branch, and `promtool` checks PromQL syntax but not Grafana dashboard JSON. The change edits one dashboard, one record and their tests by hand.

## Dependencies

- #5925: it changes the shared path `k8s/devops/dashboards/ai-spend.json`, so this change conflicts with it in that file.
- #5931: it changes the shared paths `k8s/devops/dashboards/ai-spend.json`, `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml` and `docs/TELEMETRY.md`, and its body says it replaces the 8 savings queries, so this change lands after it or is rebased on it.
- `devops_cli_ai_tokens_total` is also sent and read by `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ui/data_providers.py`, `docs/TELEMETRY.md`, `k8s/README.md`, `openspec/specs/ai-spend-pricing/spec.md`, `tests/telemetry/test_telemetry_instruments.py` and the archived change folders; this change touches the docs and the spec only.
- #5784: it changes the windows of the same 8 savings queries, and its body says it waits for this item.
- #5932: it changes the backend bar of the savings panel in the same dashboard file.
