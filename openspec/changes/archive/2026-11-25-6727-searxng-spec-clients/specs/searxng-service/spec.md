## RENAMED Requirements

- FROM: `### Requirement: Only the roadmap Service calls the pod`
- TO: `### Requirement: Only the roadmap Service and stage Jobs call the pod`

## MODIFIED Requirements

### Requirement: Only the roadmap Service and stage Jobs call the pod
NetworkPolicy `searxng-perimeter-ingress` SHALL admit TCP 8080 ingress only from the roadmap-service pods (`app.kubernetes.io/name: roadmap-service`), the stage Job pods (`app.kubernetes.io/component: roadmap-stage`), and namespace `monitoring`. No Ingress, Traefik route, or tunnel entry SHALL name the service. Only `searxng-clients` and `searxng-stage-clients` in namespace `devops` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` and `kubectl get ingress --all-namespaces`
- **THEN** the connect of the throwaway pod that is no client of the service to port 8080 is `blocked`, no Ingress has the Service `searxng` as a backend, and `uv run devops ci --check --only k8s` passes only when the roadmap-service pods (via `searxng-clients`) and the stage Job pods (via `searxng-stage-clients`) reach the service on port 8080 and the runner Job pod does not

#### Scenario: The monitoring namespace reaches the scrape port
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/devops/searxng/networkpolicy.yaml`
- **THEN** the check exits 0, the policy admits namespace `monitoring` on TCP 8080, and the runner Job pod still reaches no SearXNG port
