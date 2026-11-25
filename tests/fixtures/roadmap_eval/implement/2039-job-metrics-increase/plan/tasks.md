# Tasks

## 1. Tests First

- [ ] 1.1 Add failing tests for collector `export_created_metric: true`, Prometheus `enable-feature: created-timestamp-zero-ingestion`, and two Job runs adding up in the dashboard `increase()` query

## 2. Configuration and Documentation

- [ ] 2.1 Set `export_created_metric: true` in `k8s/otel/values.yaml`
- [ ] 2.2 Set `enable-feature: created-timestamp-zero-ingestion` in `k8s/monitoring/prometheus-values.yaml`
- [ ] 2.3 Document cluster job counter accumulation in `docs/TELEMETRY.md`

## 3. Verification

- [ ] 3.1 Verify all tests pass
- [ ] 3.2 Verify `uv run devops openspec check` passes
