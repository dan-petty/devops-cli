# Task: Expose Pyroscope UI Endpoints, Port-Forwarding, and Grafana Dashboards (#977)

**Issue**: [#977](https://github.com/dan-petty/devops-cli/issues/977)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/k8s, scope/telemetry

## Description
Following the integration of Grafana Pyroscope into the infrastructure monitoring stack (#943), users could not discover, access, or view Pyroscope continuous profiling:
1. `devops k8s deploy-stack` omitted the Pyroscope UI endpoint from its post-deployment connection summary.
2. `devops k8s port-forward` omitted `svc/pyroscope:4040` (and lacked a `--pyroscope-port` option).
3. `devops k8s configure-urls` omitted `pyroscope.url` from `_PROXY_TARGETS_INFRA` and `_NODEPORT_KEYS_INFRA`.
4. Grafana provisioned the Pyroscope datasource but lacked any continuous profiling dashboards or flamegraph panels, leaving profiling data invisible.

## Key Changes
1. **Config & Defaults**:
   - Added `DEFAULT_PYROSCOPE_URL: str = "http://localhost:4040"`, `DEFAULT_PYROSCOPE_PORT: int = 4040`, and `DEFAULT_PYROSCOPE_TIMEOUT_SECONDS: float = 5.0` to `src/devops_cli/config/defaults.py`.
   - Defined `PyroscopeConfig` model and registered `pyroscope: PyroscopeConfig = PyroscopeConfig()` in `DevOpsConfig` in `src/devops_cli/config/settings.py`.
   - Added `pyroscope_port` help text in `src/devops_cli/lang/en/help.py`.
2. **Kubernetes Networking & Port-Forwarding**:
   - Added `--pyroscope-port` option (default `4040`) to `devops k8s port-forward` in `src/devops_cli/commands/k8s/networking.py`.
   - Updated `_collect_port_forward_services` to forward `("monitoring", "svc/pyroscope", ports["pyroscope"], 4040)` for `infra` and `all` stacks.
   - Updated `_build_port_forward_details` to map `"pyroscope.url": f"http://localhost:{ports['pyroscope']}"`.
   - Added `("pyroscope.url", "monitoring", ("pyroscope",), ("4040", "http2", "http"))` to `_PROXY_TARGETS_INFRA` and `pyroscope.url` to `_NODEPORT_KEYS_INFRA`.
   - Added `pyroscope` detection to `_detect_infra_services` in `configure_urls`.
3. **Deploy-Stack Announcement**:
   - Updated `_post_deploy_credentials` in `src/devops_cli/commands/k8s/stack_lifecycle.py` to announce `Pyroscope UI: http://localhost:4040 (namespace: monitoring)` when deploying `infra` or `all` stacks.
4. **Grafana Dashboards**:
   - Created dedicated `pyroscope.json` ("Continuous Profiling / Pyroscope Flamegraphs", UID `devops-pyroscope`) with CPU, Memory In-Use, Memory Alloc, and Goroutine flamegraph panels.
   - Integrated a "Continuous Profiling & Flamegraphs (Pyroscope)" section with CPU and Memory flamegraphs into `sre-service.json`.
   - Added `pyroscope.json` to `grafana-stack-dashboards` in `k8s/monitoring/dashboards/kustomization.yaml`.
   - Verified 100% clean dashboard linting with zero errors across all 13 dashboards via `devops grafana dashboards lint`.
5. **Documentation & Tests**:
   - Documented `--pyroscope-port` in `docs/commands/k8s.md` and `k8s/README.md`.
   - Updated tests in `tests/test_k8s.py`, `tests/test_k8s_networking.py`, `tests/test_k8s_jaeger.py`, and `tests/test_k8s_monitoring_dashboards.py` with structural tuple equality assertions.

## Acceptance Criteria
- [x] `devops k8s deploy-stack` announces `Pyroscope UI: http://localhost:4040 (namespace: monitoring)`.
- [x] `devops k8s port-forward` exposes `--pyroscope-port` (default 4040) and forwards `svc/pyroscope:4040`.
- [x] `devops k8s configure-urls` discovers and maps `pyroscope.url` in proxy and nodeport modes.
- [x] `pyroscope.json` is auto-provisioned via `grafana-stack-dashboards` and `sre-service.json` includes Pyroscope flamegraph panels.
- [x] `devops grafana dashboards lint` passes with 0 errors and 0 warnings across all 13 dashboards.
- [x] Unit and integration tests pass with structural tuple equality assertions.
- [x] `uv run devops ci` quality gates pass with 100% success.
