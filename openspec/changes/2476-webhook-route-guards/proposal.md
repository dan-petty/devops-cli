# Proposal

## Why

Issue #2476: a go-live review of the roadmap Service found that its public webhook route reads the body of a delivery before it checks that the delivery has a signature header (`src/devops_cli/server/routes/webhooks.py`). Nothing in front of the route limits how many deliveries reach it (`k8s/devops/roadmap-service/ingress.yaml`), and no alert shows a burst of refused deliveries. Thus a flood of forged deliveries costs the Service CPU and log volume, and nobody sees it.

The hooks of the repositories also send more events than the Service takes. On 2026-10-28 the hook of `dan-petty/devops-cli` sent the events `issues`, `milestone`, `pull_request` and `release`. The roadmap consumer takes `issues` only, and `k8s/README.md` (Roadmap service, step 8) asks for the Issues event only, but does not say how to check a hook.

## What Changes

- The webhook route refuses a delivery with no `X-Hub-Signature-256` header, or with an empty one, with HTTP 401 `missing signature` before it reads the body. The check moves from `_authenticated_payload`, after the read, into `_refuse_before_reading`, beside the other checks of the headers. The check of a declared `Content-Length` above `CONST_SERVICE_MAX_BODY_BYTES` (25 MiB) moves into `_refuse_before_reading` too. That check already refused the delivery before the read (Feasibility), so its behavior does not change. Each refusal counts under the existing outcome `rejected`.
- The new file `k8s/devops/roadmap-service/middleware.yaml` declares the Traefik Middleware `devops/roadmap-service-rate-limit`: a `rateLimit` of 60 requests a minute, a burst of 60, and one bucket for the webhook host. The Ingress `devops/roadmap-service` names it in the annotation `traefik.ingress.kubernetes.io/router.middlewares`, in `k8s/devops/roadmap-service/ingress.yaml` and in its copy in `k8s/ingress/ingress-routes.yaml`. The kustomization of `roadmap-service` applies the Middleware, and the native `devops` stack of deploy-stack applies it before the Ingress.
- The new rule group `roadmap-service-webhooks` in `k8s/monitoring/prometheus-values.yaml` holds the warning alert `RoadmapServiceWebhooksRejected`: more than 20 deliveries rejected in 15 minutes. It is a group of its own, separate from the group `roadmap-service` of #2472.
- `k8s/README.md`, Roadmap service: step 8 says how to check the hooks (`uv run devops gh api repos/<owner>/<name>/hooks`), and that each hook sends the Issues event only. The new subsection Webhook route gives the rate limit and the refusals. The subsection Alerts and the alert table of the cluster name the new alert.
- `devops` gets no command that changes a hook. A person changes the hooks.
- The route, the manifests and the rules are observable, so the change carries a delta for the new capability `roadmap-service-webhooks` and for `roadmap-service-alerts`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `roadmap-service-webhooks`: the guards of the public webhook route of the roadmap Service: the rate limit in front of it, and the refusals before it reads a body.

### Modified Capabilities

- `roadmap-service-alerts`: a burst of rejected webhook deliveries warns.

## Impact

- Code: `src/devops_cli/server/routes/webhooks.py`, and the list of native manifests in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Manifests: `k8s/devops/roadmap-service/middleware.yaml` (new), `kustomization.yaml` and `ingress.yaml` in the same folder, and `k8s/ingress/ingress-routes.yaml`. After the merge, Argo CD's `devops` Application applies the Middleware and the changed Ingress. The CRD `middlewares.traefik.io` is already in the cluster.
- Rules: `k8s/monitoring/prometheus-values.yaml`, which Argo CD's `prometheus` Application applies.
- Tests: `tests/test_server_service.py`, `tests/test_k8s_roadmap_service.py`, `tests/test_k8s_devops_stack.py`, `tests/test_k8s_monitoring_alerting.py`, and the new promtool unit tests in `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`.
- Documents: `k8s/README.md`.

## Feasibility

Checked on 2026-10-28 against origin/main 2d38f8d8 and the homelab cluster.

- **The signature header is checked after the read: confirmed.** `_read_and_route` reads the body with `_read_capped_body`. Only then does `_authenticated_payload` read the `X-Hub-Signature-256` header and refuse a delivery without it (`webhooks.py`, lines 282-301 and 338-353). The new test sends an unsigned delivery whose body records when the route reads it, and it fails on origin/main because the route reads the body.
- **A declared length above the cap is already refused before the read: this part of the premise does not hold.** `_read_capped_body` refuses a `Content-Length` above `CONST_SERVICE_MAX_BODY_BYTES` before it reads the stream (lines 242-255), and `test_a_content_length_over_the_cap_gets_413_whatever_its_number_of_digits` pins it. The change adds no second check. It moves the existing check into `_refuse_before_reading`, and the new test pins that the route does not read the body.
- **The Traefik Middleware.** `kubectl get crd middlewares.traefik.io` gives the served version `v1alpha1`. The Traefik deployment runs `docker.io/traefik:v3.7.13` with `--providers.kubernetescrd` and `--providers.kubernetesingress`, without `safeNaming`, and with one replica. No Middleware exists. The schema of the CRD gives `rateLimit.average`, `period`, `burst` and `sourceCriterion` with `ipStrategy`, `requestHeaderName` or `requestHost`. The Traefik 3.7 documentation of the Kubernetes Ingress provider gives the annotation `traefik.ingress.kubernetes.io/router.middlewares`, and a reference of the form `<namespace>-<name>@kubernetescrd` when `safeNaming` is off. The AppProject `homelab` of Application `devops` sets no rule for namespaced kinds, so it permits a Middleware.
- **Where Traefik counts a refused request.** In the source of Traefik v3.7.13, the version of chart 41.6.0, `buildHTTPHandler` in `pkg/server/router/router.go` adds the metrics of the router to the chain before the middlewares of the router. `getLoadBalancerServiceHandler` in `pkg/server/service/service.go` adds the metrics of the service only around the proxy to each server. So a 429 of the rate limit counts in `traefik_router_requests_total`, and not in `traefik_service_requests_total`. `k8s/ingress/traefik-values.yaml` sets `addRoutersLabels: true`, and `tests/fixtures/metrics/traefik.yaml` records that the deployed Traefik serves `traefik_router_requests_total` with the labels `code` and `service`.
- **The series.** `uv run devops prometheus query 'sum by (job, event, outcome) (devops_cli_service_webhook_deliveries_total)'` gives series with `job="roadmap-service"` and the outcomes `accepted`, `ignored` and `no_subscriber`. The Service exports the counter only on its `/metrics`, through prometheus_client (`InMemoryMetricsRegistry`), so a sum does not count a delivery two times. A new label set starts at its first count, with no zero sample. k8s-monitoring scrapes `/metrics` each 60 s (`global.scrapeInterval`), so a label set has a sample each minute after its first count while its pod runs.
- **The traffic.** In the last 2 days, the Service counted at most 25 `issues` deliveries that it ignored and 11 that it accepted in one minute, and at most 85 deliveries with no subscriber. In the last 7 days, Traefik sent at most 133 requests to the Service in one minute, and none of them got a 4xx or 5xx.
- **The hooks.** `uv run devops gh api repos/dan-petty/devops-cli/hooks --jq '.[]|{id,active,events,code:.last_response.code}'` gives one active hook with the events `issues`, `milestone`, `pull_request` and `release`. The roadmap consumer takes the `issues` event only (`CONST_ROADMAP_WEBHOOK_EVENTS`).

## Existing Tool Considered

Traefik's `RateLimit` middleware, which the cluster's ingress controller already runs, limits the deliveries. The change declares it and builds no limiter. promtool, which `tools.lock` pins, tests the alert rule. The change moves two existing checks of the route and deletes the late check of the signature header in `_authenticated_payload`. It adds no code other than the tests.
