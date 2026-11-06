# Tasks

## 1. The tests of the Argo callers use the web and DNS fakes (test-only edits)

- [x] 1.1 Move `tests/argo/test_argo_gitops.py`, `tests/argo/test_argo_credentials.py`, `tests/argo/test_image_pins.py` and `tests/argo/test_argo_fleet.py` to the `web` fixture, and the sync and metric tests of the fleet and the rollout gate to their public functions
  - Verification: `uv run devops ci test tests/argo/`
- [x] 1.2 Move `tests/commands/test_argo.py`, `tests/commands/test_argo_apps_status.py` and `tests/commands/test_argo_dry_run.py` to the `web` and `dns` fixtures
  - Verification: `uv run devops ci test tests/commands/test_argo.py tests/commands/test_argo_apps_status.py tests/commands/test_argo_dry_run.py`

## 2. The tests of the Kubernetes callers use the web and DNS fakes (test-only edits)

- [x] 2.1 Move `tests/k8s/test_gitea_doctor.py` and `tests/k8s/test_k8s_service_proxy.py` to the `web` fixture
  - Verification: `uv run devops ci test tests/k8s/test_gitea_doctor.py tests/k8s/test_k8s_service_proxy.py`
- [x] 2.2 Move `tests/http/test_k8s_credentials.py` to `tests/k8s/test_k8s_credentials.py` and to the `web` and `dns` fixtures
  - Verification: `uv run devops ci test tests/k8s/test_k8s_credentials.py`
- [x] 2.3 Move the HTTP tests of `tests/ai/mcp/test_k8s_logql.py` to the `web` and `dns` fixtures
  - Verification: `uv run devops ci test tests/ai/mcp/test_k8s_logql.py`

## 3. The callers use the entry point (refactor that keeps behavior)

- [x] 3.1 Build the clients of `k8s/gitea_doctor.py`, `k8s/logql.py`, `k8s/credentials.py`, `argo/fleet.py`, `argo/rollouts.py`, `argo/gitops.py` and `commands/argo.py` with `http_client`
  - Verification: `! git grep -nE "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" -- src/devops_cli/k8s src/devops_cli/argo src/devops_cli/commands/k8s src/devops_cli/commands/argo.py`
- [x] 3.2 No test of these callers uses the old test helpers or patches `httpx2` or `socket.getaddrinfo`
  - Verification: `! git grep -nE "stub_web|public_dns|scripted_resolver|record_connects|web_fakes|StubWeb|patch\(\"httpx2|setattr\(httpx2|getaddrinfo" -- tests/argo tests/k8s tests/commands/test_argo.py tests/commands/test_argo_apps_status.py tests/commands/test_argo_dry_run.py tests/ai/mcp/test_k8s_logql.py`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3789-http-callers-k8s-argo`

## Workflow follow-up

- The other slices of #3758 move the callers of `ai`, `security`, `telemetry`, the commands and the rest, and the last slice deletes the four factories, `stub_web`, `public_dns`, `ScriptedResolver` and `tests/web_fakes.py`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
