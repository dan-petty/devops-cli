# Design

## Where the route refuses a delivery

`_refuse_before_reading` holds each check that reads only the headers, in this order:

1. The Service drains: 503 `service is draining`.
2. The content type is not JSON: 415 `unsupported media type`.
3. The event name or the delivery ID is missing: 400 `missing event or delivery header`.
4. The signature header is missing or empty: 401 `missing signature`.
5. The declared `Content-Length` is above `CONST_SERVICE_MAX_BODY_BYTES`: 413 `payload too large`.

The route reads the body only of a delivery that passes all five. The checks after the read do not change: a streamed body above the cap (413), a signature that matches no secret (401 `invalid signature`), a payload that does not validate (400), and a repository that is not managed or did not sign the body (401).

A delivery with a signature header can still be forged, so the route still reads its body to compute the HMAC. The rate limit bounds that cost.

## The rate limit

- **60 requests a minute and a burst of 60** (`average: 60`, `period: 1m`, `burst: 60`). In the last 2 days, the `issues` deliveries came at most 36 in one minute (25 ignored, 11 accepted). A burst of 60, and then 1 request each second, passes that peak with margin. Hooks that send every event added up to 85 deliveries with no subscriber in one minute, and Traefik sent at most 133 requests to the Service in one minute in 7 days. When a person sets each hook to the Issues event only (step 8), those deliveries stop. Until then, a minute of such events can get a 429 for some deliveries.
- **What a refused delivery costs.** Traefik answers a request above the limit with HTTP 429, and the Service does not see it. GitHub does not send a failed delivery again by itself. The poll of the Service starts the round that the delivery would have started, within 5 minutes by default.
- **One bucket for the host** (`sourceCriterion.requestHost: true`). Each request comes through the Cloudflare tunnel, so the remote address that Traefik sees is a `cloudflared` pod. One bucket for the host bounds the deliveries that reach the Service. That is the cost to limit: the CPU of each body's HMAC, once for each secret, and the log lines.
- Traefik runs one replica, and each replica keeps its own buckets in memory. A second replica would double the limit.

## The two copies of the Ingress

The Ingress `devops/roadmap-service` is in two files. Argo CD applies the copy in `k8s/devops/roadmap-service/ingress.yaml` through Application `devops`, and the homelab overlay of `ingress` deletes the copy in `k8s/ingress/ingress-routes.yaml`. The native `infra` stack of deploy-stack applies `ingress-routes.yaml`, and the native `devops` stack applies `ingress.yaml`. Both copies name the Middleware, so the last apply does not remove the annotation. A test reads the render of the homelab overlay of `devops` and each file that deploy-stack applies.

The Middleware is in the `devops` stack only. On a native cluster where only the `infra` stack is applied, Traefik does not build the router of the webhook route until the Middleware exists. Without the `devops` stack, no Service answers that route.

## The alert

- **A group of its own.** `roadmap-service-webhooks` is separate from `roadmap-service` (#2472), so a change of one group does not touch the lines of the other.
- **The count.** A forged delivery counts under the event that it names when the Service subscribes to that event, and under `other` when it does not. So a flood can start a new label set, and a new label set has no zero sample: `increase()` does not count its first value. The rule counts the last 15 minutes in the form of #2505. A series with no sample in the 15 minutes before counts its last value, and each other series counts its `increase()`.
- **The threshold.** More than 20 in 15 minutes, `for: 0m`, warning, as the go-live monitoring plan asks. A hook with a wrong secret gets a 401 for each delivery, and a burst of its deliveries also fires the alert. The runbook step tells the two causes apart through the hook's last response.

## Rejected alternatives

- **A bucket for each client address, from the `Cf-Connecting-Ip` header (`sourceCriterion.requestHeaderName`).** Rejected: a flood from many addresses passes it, and the cost to the Service stays the same. It keeps GitHub's deliveries apart from one address that floods, but the poll already covers a refused delivery.
- **The default source, the remote address.** Rejected: the remote address is a `cloudflared` pod, so the number of buckets follows the number of `cloudflared` replicas, not the clients. `requestHost` says what the limit counts.
- **`ipStrategy.depth` over `X-Forwarded-For`.** Rejected for the same reason as `Cf-Connecting-Ip`: it gives a bucket for each client.
- **A limit in the Service, for example with slowapi.** Rejected: the Service then still accepts each connection and parses each request, and it adds a dependency. Traefik refuses the request before it gets to the pod, and the cluster already runs Traefik.
- **A shared bucket in Valkey (`rateLimit.redis`).** Not needed: Traefik runs one replica.
- **A command that sets the events of each hook.** Rejected by the issue: the hooks stay a step for a person, and step 8 says how to check them.

## Tests

- `tests/test_server_service.py` sends each delivery with a body generator that records when the route reads it. Starlette's TestClient reads the request body only when the app calls `receive`, so the record shows whether the route read the body. A signed delivery within the cap is read and refused for its signature, which shows that the record sees a read.
- `tests/test_k8s_roadmap_service.py` renders `k8s/overlays/homelab/devops` with `kubectl kustomize`, as Argo CD does, and reads the two files that deploy-stack applies. Each Ingress names the Middleware, and the render holds the Middleware with its limit.
- `tests/test_k8s_monitoring_alerting.py` pins the rule, and `promtool test rules` runs `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` on the group.
