# Proposal

## Why

Issue #2424 is part 2 of the split of #1381. The Grafana, Prometheus and Argo CD clients in the table below build a raw `httpx2.Client`. Each one checks the host name with `validate_service_url` before the request, and httpx2 then resolves the name again at the socket. A rebinding DNS server can give a different address at the second lookup. #898 closed this window for the callers that it moved to the egress-checked factory (`devops_cli.http.client`). The Loki client and the direct cluster-service URLs already use the factory at the private level, but they still make a pre-flight check (`validate_url_egress`) that resolves the name a second time.

| Caller | Client before | Pre-flight check that goes | Level after |
| :--- | :--- | :--- | :--- |
| `devops grafana` commands | raw `httpx2.Client` (7) | `validate_service_url` in `_client_args` | configured |
| `devops prometheus` commands | raw `httpx2.Client` (5) | `validate_service_url` in `_base_url` | configured |
| `devops argo cd apps` commands | raw `httpx2.Client` (3) | `validate_service_url` in `_argocd` | configured |
| Argo CD fleet sync (`argo/fleet.py`) | raw `httpx2.Client` | `validate_service_url` | configured |
| Argo CD GitOps sync (`trigger_argocd_sync`) | raw `httpx2.Client` | `validate_service_url` | configured |
| Rollout metric gate (`argo/rollouts.py`) | raw `httpx2.Client` | `validate_service_url` | configured |
| Argo CD token mint, Grafana token mint, token check (`k8s/credentials.py`) | raw `httpx2.Client` (3) | `validate_service_url` in `_service_base_url` | configured |
| Loki (`execute_loki_query`) | factory, private | `validate_url_egress` | private |
| Direct cluster-service URL (`service_http.get_json`) | shared pool, private | `validate_url_egress` | private |

"Configured" is loopback and public addresses, and private addresses too when `ai.allow_private_network` is true (`configured_level`). Cloud metadata addresses are refused at every level.

## What Changes

- Each caller in the table gets its client from `new_http_client` at its level. The client resolves the host one time, at the connect, and dials only the addresses that its level admits. The factory checks each redirect hop in the same way.
- The pre-flight address checks in the table are deleted, and with them `_service_base_url` of `k8s/credentials.py` and the `purpose` parameter of `service_http.get_json`, which only the deleted check read.
- The mint and the check functions of `k8s/credentials.py` take an `EgressLevel` in place of the `allow_private_network` flag, whose default was `True`. `get_or_mint_argocd_token`, `get_or_mint_grafana_auth` and `sync_k8s_credentials` give `configured_level(settings.ai)`.
- An address that the level refuses is a failed step of the mint or the check, with its cause, as a request error is. The sync reports it and does not stop.
- A check that reads only the URL stays where a command needs an early error. `_clean_service_base_url` of `k8s/credentials.py` moves to `devops_cli.http.urls` as `service_base_url`. The `devops grafana`, `devops prometheus` and `devops argo cd apps` commands call it, so a `k8s://` address that `devops k8s configure-urls --addressing proxy` wrote stops the command with an error that names the setting, before any lookup.
- `devops grafana`, `devops prometheus` and `devops argo cd apps` report `SSRFBlockedError` without a traceback (`new_typer(exit_on=...)`), as they reported the pre-flight refusal. The exit status of a refusal is 2, the status of `SSRF_BLOCKED` in `docs/ERRORS.md`. The pre-flight refusal exited with status 1.
- Some levels change. Without the flag, the commands and the token calls are wider: a loopback answer, such as a `kubectl port-forward` on `localhost`, is dialled. The credential sync is narrower: before, it checked with `allow_private_network=True` whatever the flag said. Now a private Argo CD or Grafana address needs the flag in the sync too, as it does in the commands.
- `README.md`, `SECURITY.md` and `docs/KNOWN_ISSUES.md` name the moved clients. The general statement that every HTTP client is checked at the connect waits for part 5 (#2437).
- A consumer sees the levels, the refusals and the early URL error, so the change carries a spec delta.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: new requirements give the level of the Grafana, Prometheus and Argo CD clients, say that they dial the address that they checked, and say that a URL that is not HTTP stops the command before a request.
- `stack-credential-sync`: a new requirement gives the level of the token check and the mint, and makes a refused address a failed step with its cause.
- `k8s-logs`: a new requirement says that the Loki client looks up its host one time for each query.
- `k8s-service-proxy`: a new requirement says that a direct service URL looks up its host one time for each request.

## Impact

- `src/devops_cli/commands/grafana.py`, `src/devops_cli/commands/prometheus.py`, `src/devops_cli/commands/argo.py`, `src/devops_cli/argo/fleet.py`, `src/devops_cli/argo/gitops.py`, `src/devops_cli/argo/rollouts.py`, `src/devops_cli/k8s/credentials.py`, `src/devops_cli/k8s/logql.py`, `src/devops_cli/k8s/service_http.py`, `src/devops_cli/http/urls.py`, and the one caller of `get_json` that gave `purpose`, `src/devops_cli/ui/data_providers.py`.
- `tests/test_http_egress.py`, and the tests that faked the deleted checks: `tests/test_prometheus.py`, `tests/test_argo.py`, `tests/test_grafana.py`, `tests/test_argo_fleet.py`, `tests/test_k8s_credentials.py`, `tests/test_k8s_logql.py`, `tests/test_k8s_service_proxy.py`.
- `README.md`, `SECURITY.md`, `docs/KNOWN_ISSUES.md`.

## Feasibility

- On `origin/main` at `95eb8b68`, `rg -n -g '*.py' 'httpx2\.((Async)?Client|get|post|put|patch|delete|head|request|stream)\('` over the files of the issue printed 21 raw clients: `commands/grafana.py:116`, `:168`, `:233`, `:352`, `:478`, `:518`, `:555`, `commands/prometheus.py:151`, `:205`, `:294`, `:349`, `:391`, `commands/argo.py:212`, `:265`, `:294`, `argo/fleet.py:60`, `argo/gitops.py:402`, `argo/rollouts.py:92` and `k8s/credentials.py:302`, `:429`, `:511`. The `rg` for the pre-flight checks printed 9 calls: `commands/grafana.py:71`, `commands/prometheus.py:52`, `commands/argo.py:176`, `argo/fleet.py:49`, `argo/gitops.py:391`, `argo/rollouts.py:91`, `k8s/credentials.py:105`, `k8s/logql.py:384` and `k8s/service_http.py:74`.
- A raw client dials the host name. `ConnectRecorder` in `tests/web_fakes.py` stands in for `httpcore2.SyncBackend.connect_tcp`. With the new rows of `test_each_caller_dials_at_its_level` and the new `test_each_k8s_service_caller_dials_the_address_it_checked` on the code before the move, the recorder got the name `example.com` from each raw client. Without the flag, `validate_service_url` refused the loopback answer that the configured level admits.
- `validate_url_egress(url, allow_private=True)` resolves a public DNS name with `_resolve_host_ips` (`core/validation.py`) and refuses only cloud metadata. The factory backend (`VettingBackend.connect_tcp` in `http/egress.py`) resolves the name again. The new lookup test counted 2 lookups of `example.com` for one Loki query and for one direct `get_json`, on the code before the move.
- httpx2 2.13.1 refuses a URL whose scheme is not http or https with `httpx2.UnsupportedProtocol` before any lookup. So the Loki and direct cluster-service clients need no scheme check of their own. The settings type `ServiceUrlStr` admits `k8s://` addresses, and `devops k8s configure-urls --addressing proxy` writes them to `argocd.url`, `grafana.url` and `prometheus.url`. So the three command groups keep a check of the scheme that makes no lookup.
- `new_typer(exit_on=...)` (`core/cli.py`) reports the given error of each command without a traceback. `SSRFBlockedError` is a `ValueError`, so the `except ValueError` of the rollout gate and the `except Exception` of the fleet and GitOps syncs catch a refusal as they caught the pre-flight refusal.

## Existing Tool Considered

The change uses the egress-checked factory of #898 (`devops_cli.http.client`), which builds on the httpcore2 network backend API, and the `exit_on` option of `new_typer` for the error report. The early URL check is the existing `_clean_service_base_url`, moved and renamed; it uses `urllib.parse.urlsplit` and makes no lookup. The change builds no new check. It deletes these internal paths: the nine pre-flight calls in the table, `_service_base_url`, the `purpose` parameter of `get_json`, and the `allow_private_network` parameters of `mint_argocd_token`, `mint_grafana_token`, `verify_argocd_token` and `verify_grafana_token`.
