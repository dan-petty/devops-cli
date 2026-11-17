## MODIFIED Requirements

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 999, with `runAsNonRoot`, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be `emptyDir` volumes only, and `/dev/shm` SHALL be a memory volume of 1 Gi.

#### Scenario: A control is missing
- **WHEN** `uv run devops k8s lint k8s/devops/crawl4ai` runs kube-linter on the manifests, and the Deployment rolls out
- **THEN** kube-linter reports no finding for the pod, and the API server admits the pod in its namespace, which enforces Pod Security `restricted`

### Requirement: The pod holds the token and no switch that widens its reach
The environment of the container SHALL hold `CRAWL4AI_API_TOKEN` from the key `CRAWL4AI_API_TOKEN` of Secret `crawl4ai`, and `GUNICORN_BIND` set to `0.0.0.0:11235`. It SHALL set none of `CRAWL4AI_ALLOW_INTERNAL_URLS`, `CRAWL4AI_HOOKS_ENABLED` and `CRAWL4AI_EXECUTE_JS_ENABLED`, and SHALL load no Secret with `envFrom`.

#### Scenario: A switch is set
- **WHEN** a person runs `uv run devops k8s crawl4ai-check` on the cluster
- **THEN** each route refuses a request without the token, and each route refuses each internal target

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `crawl4ai-perimeter` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 11235. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `roadmap-service-to-crawl4ai` SHALL allow egress to port 11235.

#### Scenario: Another pod may call the service
- **WHEN** a person starts a throwaway pod without the label of `roadmap-service` in namespace `devops` and connects to Service `crawl4ai` on TCP 11235
- **THEN** the connect fails, and `kubectl get ingress,ingressroute -A` names no route to the service

### Requirement: The pod reaches DNS and public web pages only
NetworkPolicy `crawl4ai-perimeter` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 80 and 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter` removes. `devops-default-perimeter` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s crawl4ai-check` on the cluster
- **THEN** the throwaway pod with the label of the service opens no connection to the metadata address or to a private ClusterIP

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/crawl4ai/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/crawl4ai/`
