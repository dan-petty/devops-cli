# Task: Tempo Starts on the Chart's Own Config (#1813)

**Issue**: [#1813](https://github.com/dan-petty/devops-cli/issues/1813)
**Scope**: scope/k8s
**Feasibility**: `tempo-0` exited at start with `field compactor not found in type app.Config` (line 6) and `field ingester not found in type app.Config` (line 17). `helm template` of `grafana-community/tempo` 3.1.0 (Tempo 3.1.0) with the previous values renders those two blocks at those lines, and `grafana/tempo:3.1.0 -config.verify=true` on that render prints the same two errors. The chart's own default config for 3.1.0 uses `backend_scheduler`, `backend_worker` and `live_store`. With the values below, the render passes `-config.verify=true` (exit 0), and a container of `grafana/tempo:3.1.0` started on it logs `Tempo started`, `live-store ready to serve queries` and the retention and compaction providers.

## Description
Tempo 3 removed the `compactor` and `ingester` blocks. `k8s/otel/tempo-values.yaml` replaced the chart's `config` template with a copy of the Tempo 2 one, so the ConfigMap kept both blocks and the binary refused to start once the chart reached 3.1.0.

The values no longer override `config`. The chart builds the Tempo config from `tempo.retention` (168h, which it turns into the block retention), `tempo.reportingEnabled`, `tempo.storage` and its other values, so a later chart bump cannot leave a stale copy behind. `tempo.compactor` and the `tempo.receivers` override are gone: the chart ignores the first, and the second repeated the chart's OTLP endpoints. The chart's default receivers also open the Jaeger ports inside the pod. Its templates fail to render if `jaeger` is removed, and the `otel` namespace's NetworkPolicy admits only ports 3200, 4317 and 4318 from outside the namespace.

## Key Changes
- `k8s/otel/tempo-values.yaml`: the `config` override, `tempo.compactor` and `tempo.receivers` are removed, and a comment says why the file leaves `config` to the chart.
- `tests/test_k8s_tempo.py`: `test_tempo_runs_the_charts_own_config_so_a_chart_bump_cannot_leave_a_stale_copy` pins that the values hold no `config` and no `tempo.compactor`, and that retention is `tempo.retention`. `test_tempo_stack_contract_and_datasource_links` reads the retention from `tempo.retention`.

## Acceptance Criteria
- [x] The values hold no `config` override and no `tempo.compactor` (`test_tempo_runs_the_charts_own_config_so_a_chart_bump_cannot_leave_a_stale_copy`).
- [x] The config the values render for chart 3.1.0 passes `grafana/tempo:3.1.0 -config.verify=true`, and Tempo 3.1.0 starts on it.
- Pending a person: after the release reaches `main` and Argo CD syncs `tempo` (the Application reads its values from `main`), `kubectl -n otel get pod tempo-0` is Running and the Application is Healthy.
