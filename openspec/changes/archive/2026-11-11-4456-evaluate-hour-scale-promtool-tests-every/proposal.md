# Proposal: #4456

## Why

The promtool case `[roadmap-service-activity]` of `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` is the slowest test of the suite. It took 63.8 s on a CI runner and a median of 147 s in 24 local gate logs. Its file `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` sets `evaluation_interval: 1m`, but 7 of its 16 test groups run for 150 or 200 hours for the alert `RoadmapServiceAlternativesNotSearching`. promtool evaluates the rules of the group once each evaluation interval up to the last `eval_time` of a test group, so each of these groups makes 9,000 to 12,000 rounds. With `--dist worksteal`, the local test row cannot end before its slowest test. Closes #4456.

## What Changes

- The 7 hour-scale test groups move to a new file `tests/fixtures/prometheus_rules/roadmap_service_activity_hourly_tests.yaml` with `evaluation_interval: 1h`. The minute-scale groups stay in the old file. The cases do not change.
- One rule group can have more than one file of promtool unit tests. The promtool test runs once for each file and checks that the file tests only alerts of its group. A new test that reads the files only checks that the files of each group together test every alert of the group.
- A new guard test fails a case of a file that evaluates more than 1,000 rounds of its group (its last `eval_time` over the `evaluation_interval` of the file). It reads the durations with `devops_cli.prometheus.client.parse_duration`.
- `k8s/README.md` lists the new file and the rule for a case that runs for days.
- The change alters no behavior that a consumer observes: it changes tests, test fixtures and one document. The alert rules in `k8s/monitoring/prometheus-values.yaml` do not change. Thus it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_hourly_tests.yaml`.
- Documents: `k8s/README.md`.
- The test ids of the promtool test change from the group name to the file stem, for example `[roadmap_service_activity_tests]` and `[roadmap_service_activity_hourly_tests]`.

## Feasibility

- promtool 3.15.1 on the devcontainer host at a load average of 36 to 54 on 16 CPUs (2026-11-11): `promtool test rules` on the file of `origin/main` took 298.9 s wall and 141.1 s user CPU. On the two new files it took 1.2 s wall (1.1 s user) and 2.1 s wall (2.1 s user). All three runs printed `SUCCESS` and exited 0.
- promtool 3.15.1 accepts `evaluation_interval` at the top level of a test file only. A copy of the new file with `evaluation_interval: 1h` in one test group failed with `field evaluation_interval not found in type main.testGroup`. Thus a group of cases that needs another interval needs its own file.
- The rounds of each file of `origin/main`, by `parse_duration` of the last `eval_time` of each test group over `evaluation_interval`: `roadmap_service_activity_tests.yaml` 12,000; every other file 390 or less (`roadmap_service_tools_tests.yaml` 390, `roadmap_service_tests.yaml` 300, `research_tests.yaml` 200). After the split, the two activity files make 125 and 200.
- The rule has `for: 1h`. The files `research_tests.yaml`, `roadmap_service_tools_tests.yaml` and `ai_spend_tests.yaml` already test hour-scale rules at `evaluation_interval: 1h`.
- `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py -n0 -k "promtool or every_alert_of_the_group or unit_tested_rule"` passed 33 tests, with 5.5 s and 10.6 s for the two activity files at a load average of about 50.

## Existing Tool Considered

promtool covers the need: the change keeps `promtool test rules` and only sets its `evaluation_interval` for each file. The guard reuses `parse_duration` of `src/devops_cli/prometheus/client.py` and adds no parser. The change deletes no internal code.
