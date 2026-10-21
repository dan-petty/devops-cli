# Task: The OpenTelemetry Collector Starts After the Tempo It Exports Traces To (#409)

**Issue**: [#409](https://github.com/dan-petty/devops-cli/issues/409)
**Scope**: scope/telemetry
**Feasibility**: The collector's `otlp_grpc/tempo` exporter (`k8s/otel/values.yaml`) sends to `tempo.otel.svc.cluster.local:4317`, which #1135 put in place of Jaeger. Both deploy paths started the collector first: `_HELM_RELEASES_BY_STACK["infra"]` listed `otel-collector` before `tempo`, and `deploy-stack --wait` installs the releases in that order, and no Argo CD Application of `k8s/argocd/apps` carried a sync wave, so the `cluster` app-of-apps synced them together. A pod restart of Tempo alone while the collector runs is not a startup ordering and is not covered. The chart's own exporter retry logs each attempt, so a gate on ordering is the only way to keep the burst out of the log without silencing a real outage. A readiness gate on the collector (an init container) was not used, because it would also hold the collector's metrics and logs pipelines whenever Tempo is down at restart.

## Description

- [x] `deploy-stack` installs `tempo` before `otel-collector` in the `infra` stack, so its `--wait` leaves Tempo ready when the collector starts.
- [x] The `otel-collector` Application carries `argocd.argoproj.io/sync-wave: "1"`, so the `cluster` app-of-apps syncs it after the wave-0 Applications, `tempo` among them.
- [x] `test_the_collector_starts_after_the_tempo_it_exports_traces_to` pins both orderings against the exporter's endpoint. It fails at the base with `(True, False, False)`.
- [x] `k8s/README.md` says so where it describes Tempo.
- The collector's Loki and Prometheus exporters have the same startup dependency. Wave 1 also holds the collector until the wave-0 Applications, which include those two, are healthy. The Helm order for the logging stack (Loki) is unchanged.
- Pending a person: after the next sync of the `cluster` Application on a fresh cluster, the collector's log holds no `connection refused` burst against Tempo at startup.
