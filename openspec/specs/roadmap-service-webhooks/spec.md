# roadmap-service-webhooks Specification

## Purpose
Defines how the public webhook route of the roadmap Service guards itself: the Traefik rate limit in front of the route, and the deliveries that the route refuses before it reads their body.

## Requirements

### Requirement: The route refuses an unsigned delivery before it reads the body
The webhook route SHALL refuse a delivery with no `X-Hub-Signature-256` header, or an empty one, with HTTP 401 and the error `missing signature`, before it reads the body. It SHALL count the delivery once under the outcome `rejected`.

#### Scenario: An unsigned delivery
- **WHEN** a delivery of the `issues` event comes with no signature header
- **THEN** the route answers 401 with `{"error": "missing signature"}`
- **AND** the route does not read the body
- **AND** the deliveries counter has one `rejected` delivery of the `issues` event

#### Scenario: A delivery with an empty signature header
- **WHEN** a delivery of the `issues` event comes with an empty signature header
- **THEN** the route answers 401 with `{"error": "missing signature"}`, and does not read the body

### Requirement: The route refuses a delivery that declares a length above the cap before it reads the body
The webhook route SHALL refuse a delivery whose `Content-Length` is above `CONST_SERVICE_MAX_BODY_BYTES` with HTTP 413 and the error `payload too large`, before it reads the body. It SHALL count the delivery once under the outcome `rejected`.

#### Scenario: A delivery that declares a length above the cap
- **WHEN** a signed delivery of the `issues` event declares a `Content-Length` one byte above the cap
- **THEN** the route answers 413 with `{"error": "payload too large"}`
- **AND** the route does not read the body
- **AND** the deliveries counter has one `rejected` delivery of the `issues` event

### Requirement: The route reads the body of a signed delivery within the cap
The webhook route SHALL read the body of a delivery with a signature header and no declared length above the cap, and SHALL check its signature.

#### Scenario: A signed delivery within the cap
- **WHEN** a delivery of the `issues` event comes with a signature that no secret made
- **THEN** the route reads the body and answers 401 with `{"error": "invalid signature"}`

### Requirement: Traefik limits the deliveries of the webhook route
The Traefik Middleware `devops/roadmap-service-rate-limit` SHALL set a `rateLimit` of 60 requests a minute with a burst of 60, counted in one bucket for the request host. Each Ingress `devops/roadmap-service` that Argo CD or deploy-stack applies SHALL name it in `traefik.ingress.kubernetes.io/router.middlewares` as `devops-roadmap-service-rate-limit@kubernetescrd`.

#### Scenario: Argo CD renders the devops Application
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders the objects of Application `devops`
- **THEN** the render holds the Middleware `devops/roadmap-service-rate-limit` with `average: 60`, `period: 1m`, `burst: 60` and `sourceCriterion.requestHost: true`
- **AND** the Ingress `devops/roadmap-service` of the render names `devops-roadmap-service-rate-limit@kubernetescrd`

#### Scenario: deploy-stack applies the Ingress
- **WHEN** a test reads the Ingress `devops/roadmap-service` in `k8s/devops/roadmap-service/ingress.yaml` and in `k8s/ingress/ingress-routes.yaml`
- **THEN** each names `devops-roadmap-service-rate-limit@kubernetescrd`
- **AND** the native `devops` stack applies `middleware.yaml` before `ingress.yaml`
