# Tasks

## 1. Remote Write 2.0 Configuration

- [x] 1.1 Add failing test asserting `remote_write_version: 2` and the absence of `export_created_metric`: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] 1.2 Set `remote_write_version: 2` and remove `export_created_metric` in `k8s/otel/values.yaml`, and update comments in `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] 1.3 Update telemetry docs in `src/devops_cli/docs/generator.py` and synchronize docs: `uv run devops docs generate --sync-readme`

## 2. Verification

- [x] 2.1 Verify telemetry and k8s monitoring tests pass: `uv run devops ci test tests/test_telemetry_instruments.py tests/test_k8s_monitoring_integration.py`
- [x] 2.2 Verify docs check passes: `uv run devops docs check`
- [x] 2.3 Verify `uv run devops openspec check` passes
