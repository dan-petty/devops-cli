## MODIFIED Requirements

### Requirement: Traefik limits the deliveries of the webhook route
The Traefik Middleware `devops/roadmap-service-rate-limit` SHALL let 60 requests a minute through, with a burst of 60, in one bucket for each value of `Cf-Connecting-Ip`. Each Ingress `devops/roadmap-service` that Argo CD or deploy-stack applies SHALL name it as `devops-roadmap-service-rate-limit@kubernetescrd`. Only `k8s/devops/roadmap-service/ingress.yaml` SHALL hold the Ingress.

#### Scenario: Argo CD renders the devops Application
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders the objects of Application `devops`
- **THEN** the render holds the Middleware `devops/roadmap-service-rate-limit` with `average: 60`, `period: 1m`, `burst: 60` and `sourceCriterion.requestHeaderName: Cf-Connecting-Ip`
- **AND** the Ingress `devops/roadmap-service` of the render names `devops-roadmap-service-rate-limit@kubernetescrd`

#### Scenario: deploy-stack applies the Ingress
- **WHEN** a test reads the Ingress `devops/roadmap-service` in `k8s/devops/roadmap-service/ingress.yaml`
- **THEN** it names `devops-roadmap-service-rate-limit@kubernetescrd`
- **AND** the native `devops` stack applies `middleware.yaml` before `ingress.yaml`

#### Scenario: The environment routes hold no copy
- **WHEN** a test reads the Ingresses of `k8s/ingress/ingress-routes.yaml`
- **THEN** none of them is in namespace `devops`

## ADDED Requirements

### Requirement: Only the tunnel reaches Traefik from outside the cluster
The Traefik values SHALL keep the Service of Traefik `ClusterIP`, and the `web` entrypoint SHALL open no host port and no node port, so that each request from outside the cluster comes through Cloudflare, which writes `Cf-Connecting-Ip`.

#### Scenario: A test reads the Traefik values
- **WHEN** a test reads `k8s/ingress/traefik-values.yaml`
- **THEN** `service.spec.type` is `ClusterIP`, and `ports.web` has no `hostPort` and no `nodePort`

### Requirement: The consumer events are a subset of the hook events
Each event that a GitHub consumer of the Service takes, and each webhook event that a batch key of a due-table row names, SHALL be an event of `CONST_ROADMAP_WEBHOOK_EVENTS`, the events that `devops roadmap onboard` requires of the repository hook.

#### Scenario: A test reads the consumers of the Service
- **WHEN** a test reads the events of each GitHub consumer of `service_consumers` and the webhook batch keys of `DEFAULT_DUE_TABLE`
- **THEN** each consumer event is in `CONST_ROADMAP_WEBHOOK_EVENTS`, and each batch key event is a consumer event
