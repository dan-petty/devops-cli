# Tasks

## 1. The route refuses an unsigned or oversized delivery before it reads the body

- [x] 1.1 Write the failing test `test_the_route_reads_the_body_only_of_a_signed_delivery_within_the_cap` in `tests/test_server_service.py`, and see the unsigned cases fail because the route reads the body, with `uv run devops ci test tests/test_server_service.py`
- [x] 1.2 Move the check of the signature header from `_authenticated_payload` into `_refuse_before_reading`, and the check of the declared length from `_read_capped_body` into `_refuse_before_reading`, in `src/devops_cli/server/routes/webhooks.py`; verify with `uv run devops ci test tests/test_server_service.py`
- [x] 1.3 Add the subsection Webhook route to Roadmap service in `k8s/README.md` with the refusals; no command, option or message changes, so `uv run devops docs generate --sync-readme` changes nothing; verify with `uv run devops docs check`

## 2. Traefik limits the deliveries of the webhook route

- [x] 2.1 Write the failing test `test_each_webhook_ingress_names_the_rate_limit_that_the_devops_stack_renders` in `tests/test_k8s_roadmap_service.py`, count six manifests in `test_kustomizations_list_manifests_and_directory`, count eleven native manifests with `middleware.yaml` before `ingress.yaml` in `tests/test_k8s_devops_stack.py`, and see them fail with `uv run devops ci test tests/test_k8s_roadmap_service.py tests/test_k8s_devops_stack.py`
- [x] 2.2 Add `k8s/devops/roadmap-service/middleware.yaml`, list it in the kustomization of `roadmap-service` and in the native `devops` stack before `ingress.yaml` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), and name the Middleware in the Ingress `devops/roadmap-service` of `k8s/devops/roadmap-service/ingress.yaml` and `k8s/ingress/ingress-routes.yaml`; verify with `uv run devops ci test tests/test_k8s_roadmap_service.py tests/test_k8s_devops_stack.py tests/test_k8s_argocd_apps.py tests/test_k8s_networking.py`
- [x] 2.3 Give the rate limit in the subsection Webhook route and the Middleware in the folder tree of `k8s/README.md`; verify with `uv run devops docs check`

## 3. A burst of rejected webhook deliveries warns

- [ ] 3.1 Write the failing tests `test_the_webhook_rule_warns_on_more_than_20_rejected_deliveries_in_15_minutes` and the promtool unit tests in `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, run the selector, README and promtool tests over both groups, add the deliveries counter to `SERVED_SERIES` and the alert to the baseline, and see them fail with `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [ ] 3.2 Add the rule group `roadmap-service-webhooks` with `RoadmapServiceWebhooksRejected` to `k8s/monitoring/prometheus-values.yaml`; verify with `uv run devops ci test tests/test_k8s_monitoring_alerting.py` with the pinned promtool on `PATH`
- [ ] 3.3 Name the alert in Alerts of Roadmap service and in the alert table of `k8s/README.md`, and say in step 8 how to check the hooks and that each hook sends the Issues event only; verify with `uv run devops ci test tests/test_k8s_monitoring_alerting.py` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: set each repository's hook to the Issues event only, then check each hook with `uv run devops gh api repos/<owner>/<name>/hooks --jq '.[]|{id,active,events}'` (step 8). On 2026-10-28 the hook of `dan-petty/devops-cli` also sent `milestone`, `pull_request` and `release`.
- Pending a person: after Argo CD syncs Application `devops`, check that `kubectl -n devops get middlewares.traefik.io roadmap-service-rate-limit` exists, and that a ping of a hook still gets code 200 (Roadmap service, Go-live check, step 3).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
