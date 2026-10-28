# Tasks

## 1. The egress tests have a row for each Grafana, Prometheus, Argo CD and Loki caller

- [x] Add failing rows to `test_each_caller_dials_at_its_level` for each caller of the table, with and without `ai.allow_private_network`, and make the test fail when a caller host name reaches the dial; add `test_each_k8s_service_caller_dials_the_address_it_checked`, where each host answers a public address and then cloud metadata; add `test_loki_and_a_direct_service_url_look_up_their_host_once`; add the failing tests of the sync refusal and the Prometheus URL errors
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_k8s_credentials.py tests/test_prometheus.py`

## 2. The Grafana, Prometheus and Argo CD commands

- [x] Move `_clean_service_base_url` to `devops_cli.http.urls` as `service_base_url`, give the `devops grafana`, `devops prometheus` and `devops argo cd apps` commands factory clients at the configured level, delete their `validate_service_url` calls, check the URL with `service_base_url`, and report `SSRFBlockedError` with `exit_on`
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_grafana.py tests/test_grafana_dashboards.py tests/test_prometheus.py tests/test_argo.py`

## 3. The Argo CD fleet sync, the GitOps sync and the rollout metric gate

- [x] Give the fleet sync, the GitOps sync and the rollout metric gate factory clients at the configured level, and delete their `validate_service_url` calls
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_argo_fleet.py tests/test_argo_gitops.py tests/argo/test_gitops_fuzzing.py tests/test_argo.py`

## 4. The token mint and the token check

- [x] Give the mint and the check functions a keyword `level` in place of `allow_private_network`, give them factory clients at that level, delete `_service_base_url`, make a refused address a failed step, and give `configured_level(settings.ai)` from `get_or_mint_argocd_token`, `get_or_mint_grafana_auth` and `sync_k8s_credentials`
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_k8s_credentials.py`

## 5. Loki and the direct cluster-service URLs

- [ ] Delete the `validate_url_egress` calls of `execute_loki_query` and `service_http.get_json`
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_k8s_logql.py tests/test_k8s_service_proxy.py`

## 6. Documentation

- [ ] Name the moved clients in `README.md`, `SECURITY.md` and `docs/KNOWN_ISSUES.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 7. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2424-k8s-clients-egress-factory`

## Workflow follow-up

- Part 5 (#2437) deletes `_resolve_host_ips` and `_enforce_non_private_ssrf`, changes the kept pre-flight checks to `vet_addresses`, and writes the general statement that every HTTP client is checked at the connect.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
