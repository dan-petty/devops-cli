# Tasks

## 1. The Prometheus client (behavior)

- [x] 1.1 Add failing tests of the client: an instant query, a range query, a non-JSON answer, a failed status, a refused address, the rules and targets reads, the expression checks and the duration parser
  - Verification: `uv run devops ci test tests/prometheus/test_prometheus_client.py`
- [x] 1.2 Add `prometheus/client.py`, make the commands of `commands/prometheus.py` use it, and make `argo/rollouts.py` read the metric through `PrometheusClient.query`
  - Verification: `uv run devops ci test tests/prometheus/ tests/commands/test_prometheus.py tests/argo/test_argo_fleet.py`

## 2. The Grafana client (behavior)

- [x] 2.1 Add failing tests of the client: the reads, the import, a saved dashboard, a refused save of a provisioned dashboard (skip), a refused save of another kind (failure), a file that is not JSON, and a refused address
  - Verification: `uv run devops ci test tests/grafana/test_grafana_client.py`
- [x] 2.2 Add `grafana/client.py`, make the commands of `commands/grafana.py` use it, and lower the ceiling of `commands/grafana.py` in the swallowed-failures ratchet
  - Verification: `uv run devops ci test tests/grafana/ tests/commands/test_grafana.py`

## 3. The Argo CD client (behavior)

- [x] 3.1 Add failing tests of the endpoint (a stored token, a missing token, a masked token, a missing URL, an address the client cannot dial, the configured level) and of `check_application_pins`
  - Verification: `uv run devops ci test tests/argo/test_argo_client.py tests/argo/test_image_pins.py`
- [x] 3.2 Add `argo/client.py` and `check_application_pins`, and make `commands/argo.py`, `argo/fleet.py` and `argo/gitops.py` use them
  - Verification: `uv run devops ci test tests/argo/ tests/commands/test_argo.py tests/commands/test_argo_apps_status.py tests/commands/test_argo_dry_run.py`

## 4. The tests use the HTTP fake and the other edge fakes (test-only edits)

- [x] 4.1 Move `tests/argo/test_argo_fleet.py`, `tests/argo/test_argo_gitops.py` and the PromQL tests to the `web`, `cluster`, `process_fake`, `mcp_dispatcher` and `cli` fixtures, and move `tests/commands/test_promql_analysis.py` to `tests/prometheus/`
  - Verification: `uv run devops ci test tests/argo/ tests/prometheus/ tests/commands/test_prometheus.py`
- [x] 4.2 The three migrated test files hold no patch site, no private import and no module-level `CliRunner`
  - Verification: `! git grep -n -e unittest.mock -e monkeypatch.setattr -e CliRunner -e "import _" -- tests/argo/test_argo_fleet.py tests/argo/test_argo_gitops.py tests/prometheus/test_promql_analysis.py`
- [x] 4.3 No command file builds a client, and the rollout gate holds no copy of the instant query
  - Verification: `! git grep -n -e new_http_client -e httpx2.Client -e http_client -e /api/v1/query -- src/devops_cli/commands/prometheus.py src/devops_cli/commands/grafana.py src/devops_cli/commands/argo.py src/devops_cli/argo/rollouts.py`

## 5. Documents

- [x] 5.1 Name the three clients in `ARCHITECTURE.md` and link them in the Grafana and Prometheus pages of the knowledge base
  - Verification: `uv run devops ci docs`

## 6. Archive

- [ ] 6.1 Archive the change
  - Verification: `uv run devops openspec archive 3754-argocd-promql-grafana-on-http-fake`

## Workflow follow-up

- The `_client_args` test of `tests/commands/test_grafana.py` still patches two names. The patch sites in the other command test files belong to the finish of #1327. #1335 ("Found while measuring") says that a person decides whether to reopen #1327 or file a new item.
- `test_inspect_git_manifest_drift_handles_spaces_non_ascii_and_renames` in `tests/argo/test_argo_gitops.py` starts the real `git`. A transcript scenario for it is a later item.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
