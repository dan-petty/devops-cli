# Proposal

## Why

Issue #3789 is one slice of #3758, which is part 3 of #1314. After parts 1 and 2, the callers in `src/devops_cli/k8s/`, `src/devops_cli/argo/` and `src/devops_cli/commands/argo.py` still build their HTTP clients with `new_http_client`. Their tests still reach HTTP through `stub_web`, `public_dns`, `scripted_resolver`, `record_connects`, and patches of `httpx2.Client` and of `devops_cli` names. The four old factories can go only when every caller has moved, so this slice moves its callers and leaves the deletion to the last slice of #3758.

## What Changes

- Callers: `k8s/gitea_doctor.py`, `k8s/logql.py`, `k8s/credentials.py` (3 sites), `argo/fleet.py`, `argo/rollouts.py`, `argo/gitops.py` and `commands/argo.py` (2 sites) build their clients with `http_client` from `devops_cli.http.entry`. Each keeps its egress level, timeout and redirect rule. `argo/image_pins.py` only names the client type, and `k8s/service_http.py` already uses the entry point.
- Tests: the tests of these callers use the `web` fixture (`WebFake`) and the `dns` fixture (`DnsFake`) in place of `stub_web`, `public_dns`, `scripted_resolver`, `record_connects`, and patches of `httpx2.Client` and `socket.getaddrinfo`. A test of the HTTP part patches no `devops_cli` name.
  - `tests/argo/test_argo_gitops.py`, `tests/argo/test_argo_fleet.py` and `tests/commands/test_argo.py` read their settings through the `config` and `keyring_store` fixtures. They no longer patch `load_settings`, `get_argocd_token` or `httpx2.Client`.
  - `tests/argo/test_argo_fleet.py` tests the Argo CD sync of a fleet target and the metric read of the rollout gate through their public functions, `sync_single_target` and `evaluate_rollout_gate`, not through the private `_execute_cluster_sync` and `_fetch_metric_value`.
  - `tests/commands/test_argo_dry_run.py` asserts, with the `web` and `dns` fakes, that a dry run sends no request and makes no lookup.
  - `tests/k8s/test_k8s_service_proxy.py` fetches through the `web` fake in place of a `MagicMock` client.
  - `tests/ai/mcp/test_k8s_logql.py` answers Loki through the `web` fake. The refusal tests read the requests that reached the fake in place of the dials of a connect recorder.
  - `tests/http/test_k8s_credentials.py` moves to `tests/k8s/test_k8s_credentials.py`, the mirror of `src/devops_cli/k8s/credentials.py`.
- Not changed: the four old factories, `stub_web`, `public_dns`, `scripted_resolver` and `tests/web_fakes.py`. Callers outside these packages still use them. The last slice of #3758 deletes them.
- This change alters no behavior a consumer observes: no command, option, message or request changes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `src/devops_cli/k8s/` (`gitea_doctor.py`, `logql.py`, `credentials.py`), `src/devops_cli/argo/` (`fleet.py`, `rollouts.py`, `gitops.py`) and `src/devops_cli/commands/argo.py`.
- `tests/argo/`, `tests/k8s/`, `tests/commands/test_argo.py`, `tests/commands/test_argo_apps_status.py`, `tests/commands/test_argo_dry_run.py` and `tests/ai/mcp/test_k8s_logql.py`.

## Feasibility

Checked on `origin/main` 27c7019f, 2026-11-06. The premise of #3758 holds for this slice. The tree has moved since the issue was written, so each claim was read again.

- The callers of the factories in this slice are found by `git grep -nE "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" -- src/devops_cli/k8s src/devops_cli/argo src/devops_cli/commands/k8s src/devops_cli/commands/argo.py` on `origin/main`. It lists `k8s/gitea_doctor.py`, `k8s/logql.py`, `k8s/credentials.py`, `argo/fleet.py`, `argo/rollouts.py`, `argo/gitops.py` and `commands/argo.py`. `k8s/service_http.py` already uses the entry point (#3755). No module in `commands/k8s/` builds a client.
- `http_client(level, *, timeout=..., **options)` in `src/devops_cli/http/entry.py` takes the same arguments as `new_http_client`, with `level` as the first argument, and builds the client with the same function when no `key` is given. So a move changes no timeout, limit or redirect rule.
- The `web` fixture installs the fake as the transport of every client that the entry point builds. It vets each host at the client's egress level, so the tests that check a refused address (#2424) keep their meaning. The `dns` fixture serves the lookups of those tests.
- Two tests held a false premise that the move showed. `test_argo_commands_execution` mocked the Argo CD answers, but its first command turns the global dry run on, and the `cd apps` commands that follow send no request. The mock was never read. The test now says so and asserts that no request reached the fake. `tests/argo/test_argo_fleet.py` and `tests/commands/test_argo_dry_run.py` patched the whole `httpx2.Client` class, so no request was ever checked against a level.
- Environment: the test configuration sets `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` (`tests/conftest.py`). A test that needs the loopback level sets the variable to `false` with `monkeypatch.setenv` before it calls `config`.

## Existing Tool Considered

Not applicable: this slice builds nothing. It uses the entry point and the fakes of parts 1 and 2 of #1314: `http_client` (`src/devops_cli/http/entry.py`), `WebFake` over httpx2's `MockTransport`, and `DnsFake`. The change deletes no internal code of its own. It removes the last uses of the old factories in these packages, so the final slice of #3758 can delete them.
