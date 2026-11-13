## MODIFIED Requirements

### Requirement: Traefik limits the deliveries of the webhook route
The Traefik Middleware `devops/roadmap-service-rate-limit` SHALL set a `rateLimit` of 60 requests a minute with a burst of 60, counted in one bucket for the request host. Each Ingress `devops/roadmap-service` that Argo CD or deploy-stack applies SHALL name it in `traefik.ingress.kubernetes.io/router.middlewares` as `devops-roadmap-service-rate-limit@kubernetescrd`. Only `k8s/devops/roadmap-service/ingress.yaml` SHALL hold the Ingress.

#### Scenario: Argo CD renders the devops Application
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders the objects of Application `devops`
- **THEN** the render holds the Middleware `devops/roadmap-service-rate-limit` with `average: 60`, `period: 1m`, `burst: 60` and `sourceCriterion.requestHost: true`
- **AND** the Ingress `devops/roadmap-service` of the render names `devops-roadmap-service-rate-limit@kubernetescrd`

#### Scenario: deploy-stack applies the Ingress
- **WHEN** a test reads the Ingress `devops/roadmap-service` in `k8s/devops/roadmap-service/ingress.yaml`
- **THEN** it names `devops-roadmap-service-rate-limit@kubernetescrd`
- **AND** the native `devops` stack applies `middleware.yaml` before `ingress.yaml`

#### Scenario: The environment routes hold no copy
- **WHEN** a test reads the Ingresses of `k8s/ingress/ingress-routes.yaml`
- **THEN** none of them is in namespace `devops`
