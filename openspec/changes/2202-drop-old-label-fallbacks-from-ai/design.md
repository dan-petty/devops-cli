# Design

## Decisions

- **Drop the `label_replace` that sets `operation` to `chat` and sum each operation branch by operation and type.**: The `operation` label came before the `local` label, so every series with `local="true"` carries it, as `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml:14:` says with `the labels came with #1623`, and the staged `docs/TELEMETRY.md:110:` line says the counter is `by operation (chat or embeddings)`; the label_replace then maps no absent label.
- **Keep the fallback check in `_misses_a_local_token_or_the_price` and make it fail when a savings query holds a fallback selector.**: The second acceptance criterion says the savings queries name no series without `local`, and the staged guard checked only the selectors and the `label_replace` clause, so dropping that clause alone would let a kept fallback pass. The group replaces it with the absence of `local=""` and `provider="gateway", server!="cache"`, which fails on all 8 queries before they are rewritten.
- **Keep two operation branches per query instead of one `local="true"` selector.**: The price vector is joined on operation and type, so the two branches keep the query shape that the spec names and the change is one removed disjunct and one removed wrapper per query.
- **Keep one record, the 2-day range to 2026-10-24T22:00:00Z, with its four `local="true"` series.**: The new query selects no series in the 21-day range, whose series carry no label, and the key of the deleted price rule described only that range.
- **Set the record's `result` to the priced total of its kept series.**: The test computes the same total from the same series and the dashboard constant, so the value is checked; no runner reaches Prometheus, and a person records the live answer with the acceptance check.
- **Keep the `server!="cache"` matcher of the Tokens Processed in Range panel and of `openspec/specs/gateway-caller-telemetry/spec.md`.**: It selects devops-cli's own token series that bypassed the gateway, and not a savings query, and that requirement holds the panel's query.
- **State the record's rule in the modified requirement with the labels and the price constant in code spans, and give the record's check as the test command in its scenario.**: The record is a case file that only a `manifest` group changes, so no behavior group can name the deleted key or the price constant; the scenario names the command that checks the record instead, which `src/devops_cli/roadmap/stage/stage_change.py:def _is_scenario_command` exempts from the behavior-test rule.

## Rejected alternatives

- **Drop the `label_replace` clause from `_misses_a_local_token_or_the_price` and add no fallback check.**: `tests/prometheus/test_k8s_monitoring_dashboards.py:424:` `or '"operation", "chat", "", ""' not in expr` is the only assertion about the fallback in the staged test, so removing it would leave the 8 queries unguarded and a kept `local=""` disjunct would pass, which the issue's second criterion forbids.
- **Keep the `label_replace` and drop only the `local=""` disjuncts.**: The `label_replace` exists to give a summed vector the label `chat`, and with `local="true"` alone every selected series has `operation`; keeping it would leave the text that the issue calls dead code in the 8 queries.
- **Change the dashboard in one group and the record in another.**: `tests/prometheus/test_k8s_monitoring_dashboards.py:499:` holds `== ([_savings_record()["expr"]], total.quantize(to_the_micro_dollar))`, so a group that changes only one of the two fails its own verify.
- **Wait for the open pull request that replaces the savings queries and delete the panels instead.**: The pull request is open and unmerged, and `k8s/devops/dashboards/ai-spend.json:145:` still holds the fallback at the staging commit, so the removal applies to the file as it stands; `dependencies` names the conflict.
- **Name the price constant in a code span of the record's scenario and add a behavior group that names it.**: The constant lives in `k8s/devops/dashboards/ai-spend.json` and in no `src/` file, so only a `manifest` group edits it; a behavior group has no code to change, and the scenario names the test command instead.

## Unchanged references

- `openspec/specs/gateway-caller-telemetry/spec.md` (query literal): It holds `server!="cache"` for the Tokens Processed in Range panel, which selects devops-cli's own series that bypassed the gateway, and no savings query.

## Security

Nothing new crosses a trust boundary: the change removes label matchers from read-only PromQL in a provisioned dashboard and edits the record and tests that read it, and it adds no host, no secret and no new egress. A person must confirm that the removed fallback read no series the dashboard still needs, and that the generated ConfigMap of `k8s/devops/dashboards/ai-spend.json` stays under the 262,144-byte last-applied annotation limit. `_misses_a_local_token_or_the_price` in `tests/prometheus/test_k8s_monitoring_dashboards.py` fails when a savings query holds `local=""` or `provider="gateway", server!="cache"`, and `test_each_configmap_fits_kubectls_last_applied_annotation` fails when a ConfigMap reaches the limit.
