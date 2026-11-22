## MODIFIED Requirements

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `crawl4ai-perimeter-ingress` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 11235. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `roadmap-service-to-crawl4ai` SHALL allow egress to port 11235.

#### Scenario: Another pod may call the service
- **WHEN** a throwaway pod with no label in namespace `devops` runs `nc -w 3 crawl4ai.devops.svc.cluster.local 11235`, started with `kubectl run --rm -i --restart=Never`, and a person runs `kubectl get ingress --all-namespaces`
- **THEN** the connect times out, and no Ingress has the Service `crawl4ai` as a backend

### Requirement: The pod reaches DNS and public web pages only
NetworkPolicy `crawl4ai-perimeter-egress` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 80 and 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter-egress` removes. `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s crawl4ai-check`
- **THEN** the connects of the throwaway pod with the label of `crawl4ai` to the metadata address and to a private ClusterIP are `blocked`, and the command exits 0
