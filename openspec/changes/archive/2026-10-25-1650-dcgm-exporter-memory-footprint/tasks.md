# Tasks

## 1. Configure DCGM exporter resources

- [x] 1.1 Add failing assertion for dcgm-exporter resources in `tests/test_k8s_monitoring_integration.py`. Verification: `uv run pytest tests/test_k8s_monitoring_integration.py -k test_dcgm_exporter_is_scraped_by_the_integration_and_holds_sys_admin`.
- [x] 1.2 Add explicit resource requests and limits with measurement comment to `k8s/monitoring/dcgm-exporter-values.yaml`. Verification: `uv run pytest tests/test_k8s_monitoring_integration.py -k test_dcgm_exporter_is_scraped_by_the_integration_and_holds_sys_admin`.
- [x] 1.3 Regenerate documentation and verify that documentation remains clean. Verification: `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- ContainerMemoryNearLimit alerting rule is tracked in follow-up issue #1392.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
