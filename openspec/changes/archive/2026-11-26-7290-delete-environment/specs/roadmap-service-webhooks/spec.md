## ADDED Requirements

### Requirement: Traefik limits the deliveries of the product webhook route
The Traefik Middleware `devops/roadmap-service-rate-limit` SHALL let 60 requests a minute through, with a burst of 60, in one bucket for each value of `Cf-Connecting-Ip`. Each Ingress `devops/roadmap-service` that Argo CD or deploy-stack applies SHALL name it as `devops-roadmap-service-rate-limit@kubernetescrd`. Only `k8s/devops/roadmap-service/ingress.yaml` SHALL hold the Ingress.

#### Scenario: Argo CD renders the devops Application
- **WHEN** `kubectl kustomize k8s/devops` renders the objects of Application `devops`
- **THEN** the render holds the Middleware `devops/roadmap-service-rate-limit` with `average: 60`, `period: 1m`, `burst: 60` and `sourceCriterion.requestHeaderName: Cf-Connecting-Ip`
- **AND** the Ingress `devops/roadmap-service` of the render names `devops-roadmap-service-rate-limit@kubernetescrd`

#### Scenario: deploy-stack applies the Ingress
- **WHEN** a test reads the Ingress `devops/roadmap-service` in `k8s/devops/roadmap-service/ingress.yaml`
- **THEN** it names `devops-roadmap-service-rate-limit@kubernetescrd`
- **AND** the native `devops` stack applies `middleware.yaml` before `ingress.yaml`

## REMOVED Requirements

### Requirement: Traefik limits the deliveries of the webhook route
**Reason**: One scenario of it read the Ingresses of the environment tree (#7290).
**Migration**: See `Traefik limits the deliveries of the product webhook route`.

### Requirement: Only the tunnel reaches Traefik from outside the cluster
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
