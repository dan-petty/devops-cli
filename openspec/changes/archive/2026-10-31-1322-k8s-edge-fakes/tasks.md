# Tasks

## 1. Source refactoring

- [x] Move `_apply_configured_k8s_context` to `src/devops_cli/k8s/context.py` as public `apply_configured_k8s_context` and call it from `src/devops_cli/commands/devcontainer.py`
  - Verification: `rg -n 'apply_configured_k8s_context' src/devops_cli/k8s/context.py src/devops_cli/commands/devcontainer.py`
- [x] Route `doctor.get_k8s_client` and `service_proxy.resolve_proxy_target` through `KubernetesService`
  - Verification: `rg -n 'CoreV1Api|load_kube_config|load_incluster' src/devops_cli/k8s/service_proxy.py src/devops_cli/k8s/doctor.py`
- [x] Make internal helpers public in `src/devops_cli/k8s/` (`parse_kyverno_output`, `parse_opa_output`, `parse_text_falco_alert`, `tally_severity_counts`, `get_severity_color`, `sort_findings`, `transport_key`, `ssl_context`)
  - Verification: `rg -n 'def (parse_kyverno_output|parse_opa_output|parse_text_falco_alert|tally_severity_counts|get_severity_color|sort_findings|transport_key|ssl_context)\b' src/devops_cli/k8s/`

## 2. Test splits and migrations

- [x] Move manifest invariants from `test_k8s_push_secrets.py` and `test_k8s_argocd_overrides.py` to `tests/invariants/test_k8s_manifests.py`
  - Verification: `uv run pytest tests/invariants/test_k8s_manifests.py`
- [x] Split `test_k8s_push_secrets.py` into `tests/k8s/test_cluster_secret_push.py` and `tests/k8s/test_cluster_secret_plan.py` over `process_fake` and `keyring_store`
  - Verification: `uv run pytest tests/k8s/test_cluster_secret_push.py tests/k8s/test_cluster_secret_plan.py`
- [x] Move HTTP connection pool tests from `tests/k8s/test_http_connection_pool.py` to `tests/http/test_http_connection_pool.py`
  - Verification: `uv run pytest tests/http/test_http_connection_pool.py`
- [x] Move `_build_pods_table` unit tests to CLI tests in `tests/commands/k8s/test_k8s.py`
  - Verification: `rg -n '_build_pods_table' tests/k8s/`
- [x] Move FastMCP security stream tool tests to `tests/ai/mcp/test_fastmcp_contracts.py`
  - Verification: `uv run pytest tests/ai/mcp/test_fastmcp_contracts.py`

## 3. Test isolation and edge fakes

- [x] Migrate `tests/k8s/test_k8s_chaos_runner.py` to `process_fake` and rename test functions
  - Verification: `uv run pytest tests/k8s/test_k8s_chaos_runner.py`
- [x] Migrate `tests/k8s/test_k8s_logs_diff_chaos.py` to `process_fake` and `cli` fixture
  - Verification: `uv run pytest tests/k8s/test_k8s_logs_diff_chaos.py`
- [x] Migrate `tests/k8s/test_k8s_policy.py` to `process_fake` and `cli` fixture
  - Verification: `uv run pytest tests/k8s/test_k8s_policy.py`
- [x] Migrate `tests/k8s/test_k8s_template.py` to `process_fake`, Syrupy snapshots, and config environment
  - Verification: `uv run pytest tests/k8s/test_k8s_template.py`
- [x] Migrate `tests/k8s/test_k8s_service.py` to `clock` fake and rename test functions
  - Verification: `uv run pytest tests/k8s/test_k8s_service.py`
- [x] Migrate `tests/k8s/test_k8s_service_proxy.py` to `cluster` fake and `cli` fixture
  - Verification: `uv run pytest tests/k8s/test_k8s_service_proxy.py`
- [x] Migrate `tests/k8s/test_k8s_doctor.py` to `cluster` fake and `cli` fixture
  - Verification: `uv run pytest tests/k8s/test_k8s_doctor.py`
- [x] Migrate `tests/k8s/test_k8s_port_forward_daemon.py` to `DEVOPS_CLI_DATA_DIR` and `cli` fixture
  - Verification: `uv run pytest tests/k8s/test_k8s_port_forward_daemon.py`
- [x] Migrate `tests/k8s/test_k8s_context_resolution.py` to `process_fake` and public `apply_configured_k8s_context`
  - Verification: `uv run pytest tests/k8s/test_k8s_context_resolution.py`
- [x] Migrate `tests/k8s/test_k8s_security_stream.py` to `process_fake` and remove internal patches
  - Verification: `uv run pytest tests/k8s/test_k8s_security_stream.py`
- [x] Rename non-standard test names across `tests/k8s/`
  - Verification: `rg -n 'def test_.*_(success|failure|basic|command)\b' tests/k8s/`

## 4. Verification and quality gate

- [x] Confirm zero devops_cli internal patches and zero private imports in `tests/k8s/`
  - Verification: Run AST audit on `tests/k8s/`
- [x] Run full CI and pass all checks
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change
  - Verification: `uv run devops openspec archive 1322-k8s-edge-fakes`
