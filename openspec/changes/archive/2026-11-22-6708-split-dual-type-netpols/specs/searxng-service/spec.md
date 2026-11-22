## MODIFIED Requirements

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `searxng-perimeter-ingress` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 8080. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `searxng-clients` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` and `kubectl get ingress --all-namespaces`
- **THEN** the connect of the throwaway pod that is no client of the service to port 8080 is `blocked`, and no Ingress has the Service `searxng` as a backend
- **AND** `uv run devops ci --check --only k8s` passes only when the Service pod and the stage Job pod reach the service and the runner Job pod does not

### Requirement: The pod reaches DNS and public HTTPS only
NetworkPolicy `searxng-perimeter-egress` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter-egress` removes. `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** the connects of the throwaway pod with the label of `searxng` to the metadata address and to a private ClusterIP are `blocked`, and the search rows return hits from the public engines
