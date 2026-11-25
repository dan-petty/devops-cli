# Proposal

## Why

Issue #4709 asks for the first SLO source of the project. The roadmap Service, its runner Jobs and the LLM gateway have an objective and a 28-day window in `k8s/README.md`, and no rule records them: `k8s/README.md:651:The rows stay here until the Sloth specs of #4709 hold them.` The project review, the pipeline dashboard and the design spec need one source for the four SLOs, their error budgets and their burn-rate alerts. The change makes the spec that source, renders it into the rule file that the server already loads, and fails the `k8s` row when the file is not the render.

## What Changes

- Add `src/devops_cli/prometheus/slo_rules.py`, which reads a Sloth `prometheus/v1` spec and renders its SLI recording rules and the four burn-rate alerts of the 28-day window, each alert guarded by at least 20 events in its long window.
- Add one Sloth spec for each of the four SLOs under `k8s/devops/monitoring/slos/`, each naming a service that the catalog data holds, its objective and the 28-day window, with the runner Jobs caveat in the description of the second SLO.
- Add `tests/gate/k8s_checks/slo_rules.py` to the `k8s` row: each spec names a catalog service, the four `slo-` groups of the product rule file equal a fresh render, each of the four SLO rows of `k8s/README.md` names its spec, and each SLO alert has a runbook row.
- Add the four `slo-` groups to `k8s/devops/monitoring/prometheus-rules-values.yaml`, the product rule file that the server already loads.
- Add one promtool case file for each SLO under `tests/fixtures/prometheus_rules/`, list the four groups in `RULE_GROUP_TESTS`, and add the five raw metrics and the SLO record names to `SERVED_SERIES`.
- Name the spec in each of the four SLO rows of `k8s/README.md` and drop their objectives there, keep the SLO 5 objective, and add a row to the Alerting table for each of the 16 alerts.
- Put the specs and the rule groups in the product folder `k8s/devops/monitoring/`, which the environment-freeze check admits, because the environment tree now lives in dan-petty/homelab.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `product-monitoring-content`: One Sloth spec for each SLO of the product, The SLO rule groups are the output of the renderer, Each burn-rate alert needs 20 events in its long window, One promtool case file for each SLO, One place for each SLO objective, A runbook row for each SLO alert, The product alert rules have their own values file, The monitoring tests count each recorded series as served

## Impact

- Code: `src/devops_cli/prometheus/slo_rules.py`, `k8s/devops/monitoring/slos/roadmap-service-rounds.yaml`, `k8s/devops/monitoring/slos/runner-jobs-duration.yaml`, `k8s/devops/monitoring/slos/llm-gateway-requests.yaml`, `k8s/devops/monitoring/slos/llm-gateway-latency.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/gate/k8s_checks/slo_rules.py`, `tests/gate/k8s.py`, `tests/commands/k8s/test_k8s.py`, `tests/fixtures/prometheus_rules/slo_roadmap_service_rounds_tests.yaml`, `tests/fixtures/prometheus_rules/slo_runner_jobs_duration_tests.yaml`, `tests/fixtures/prometheus_rules/slo_llm_gateway_requests_tests.yaml`, `tests/fixtures/prometheus_rules/slo_llm_gateway_latency_tests.yaml`

## Feasibility

- The probes confirm the cited files: "The path `k8s/monitoring/prometheus-values.yaml` is a file of the staging commit.", "The path `k8s/README.md` is a file of the staging commit." and "The path `k8s/catalog.toml` is a file of the staging commit.", and they show that the rule file of the issue is new: "The path `k8s/monitoring/slo-rules-values.yaml` is no file of the staging commit. No commit in the history deleted or renamed it."
- The pin of the issue cannot be built: "The path `src/devops_cli/tools_lock/tools.lock` is no file of the staging commit. No commit in the history deleted or renamed it.", so no group adds a lock entry, and `search_code sloth` returned no line of `src/`, so no group runs `sloth`.
- The paths of the issue cannot change here: `tests/gate/k8s_checks/environment_freeze.py:def is_environment_path` refuses each non-Markdown file of `k8s` outside `k8s/devops` and `k8s/overlays/homelab/devops`, so a spec, a rule file or a dashboard under `k8s/monitoring` fails the `k8s` row that `Static Analysis` runs. The specs and the four groups therefore go in the product folder `k8s/devops/monitoring/`.
- `docs/guidelines/sre.md:52:The window is 28 days for each SLO.` gives the window, and `docs/guidelines/sre.md:64:| Page | 1 h | 5 min | 2 % | 13.44 |` to `docs/guidelines/sre.md:67:| Ticket | 3 d | 6 h | 10 % | 0.93 |` give the four alert rows.
- `docs/guidelines/sre.md:54:An SLO with fewer than 20 events in the long window of an alert gives` gives the 20-event guard, and `docs/guidelines/sre.md:71:An SLO with fewer than 20 events in 1 hour gets no page alert, because of the low-sample rule.` gives the case of the stage row that the comment of 2026-11-13 asks for.
- `docs/guidelines/sre.md:44:A Sloth spec names its service, and the service dashboard table names its workload, so the catalog data holds no SLO and no dashboard.` keeps each spec on a catalog service, and `k8s/catalog.toml:23:name = "roadmap-service"` shows the names that the four specs use.
- `k8s/README.md:651:The rows stay here until the Sloth specs of #4709 hold them.` and `k8s/README.md:661:SLO 2 counts only the runner Jobs that end.` show that the spec becomes the one place of each objective and of the caveat.
- `k8s/README.md:659:| 5 | Roadmap Service |` is the SLO 5 row, which keeps its objective and gets no spec in this change, so the README check names the four SLO rows of this change only and leaves that row alone.
- `docs/guidelines/sre.md:77:Each alert has a runbook row` gives the runbook rule, and `k8s/devops/monitoring/prometheus-rules-values.yaml:10:# server loads this file next to the environment rules. A group name is unique over both files.` shows that the server already loads the product file.
- `tests/prometheus/test_k8s_monitoring_alerting.py:157:MAX_PROMTOOL_ROUNDS = 1_000` bounds each case, `tests/prometheus/test_k8s_monitoring_alerting.py:599:step = parse_duration(str(unit_tests.get("evaluation_interval", "1m")))` reads the rule step of a case file, and 3 days at 5 minutes makes 864 rounds, under the bound.
- `tests/prometheus/test_k8s_monitoring_alerting.py:190:SERVED_SERIES = frozenset(` and `tests/prometheus/test_k8s_monitoring_alerting.py:def test_every_alert_rule_selects_only_series_the_stack_serves` refuse an expression whose selector names a series outside the set, so the record names of the four groups and their raw metrics join the set.
- `tests/gate/k8s.py:def main` runs each check function of `tests/gate/k8s_checks`, so the new module joins the `k8s` row with no new subcommand.
- `load_slo_specs`, `render_slo_groups` and `write_slo_groups` need a checkout of the repository, no client of a service and no network: they read and write files of the checkout.
- `promtool` is a runner tool of the image, so each case test carries the live mark of `promtool` and runs under `runAsNonRoot: true`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true` and `seccompProfile: RuntimeDefault`; a rule or a case that `promtool` refuses fails the class `test`, which the step repairs.
- `kubectl` is a runner tool, so the `k8s` row runs under the same pod settings, and a stale render, an unknown catalog service or a missing runbook row fails the class `test`; `sloth` is in neither the runner tools nor `NOT_IN_RUNNER`, so no step runs it.
- The first checks against the real system are `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` and `uv run devops ci --check --only k8s`.
- Not checked: the measured values of the issue, its claim that the cluster runs no Prometheus operator, the live return of `slo:sli_error:ratio_rate1h` after the Argo CD sync, and the service dashboards of the comment of 2026-11-13, which live in dan-petty/homelab. This run read no cluster and queried no Prometheus, so only a person confirms the live criterion after the merge.

## Existing Tool Considered

Sloth v0.16.0 (Apache-2.0) covers the need: one `prometheus/v1` spec becomes the SLI recording rules and the multi-window, multi-burn-rate alerts, and it runs as a one-shot CLI, so no running service or UI is added. The runner image holds no `sloth` program, `src/devops_cli/roadmap/runner_tools.py` lists none, and a live check may not need a program that neither table holds, so this change renders the same spec format in `src/devops_cli/prometheus/slo_rules.py`: about 12k tokens to build, 3k tokens a year to keep and repair, and 1 day elapsed. It deletes no internal code. Pyrra v0.10.2 stays out: it adds a running service and a UI that the project does not need.

## Dependencies

- `devops_cli_service_jobs_total`: the cited metric also sits in `src/devops_cli/config/constants.py`, `src/devops_cli/docs/generator.py` and `src/devops_cli/roadmap/project_review/catalog.yaml`; the SLO rule reads it by its `result` label, as the recording group of `k8s/devops/monitoring/prometheus-rules-values.yaml` already does, so none of those files changes.
