# crawl4ai-service Specification

## Purpose
How the Crawl4AI page-text service runs in namespace `devops`: its pod controls, the pinned image, who may call it, and where it may connect. The service renders pages that a model chose, so its network perimeter is the main control against a request to an internal address.

## Requirements

### Requirement: The Deployment pins the image by release and digest
Deployment `crawl4ai` in `k8s/devops/crawl4ai/deployment.yaml` SHALL run one container whose image is `unclecode/crawl4ai:<release>@sha256:<digest>`, with one replica and the `Recreate` strategy.

#### Scenario: The image names a tag only
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops`
- **THEN** the command resolves the image of Deployment `crawl4ai` by its digest at the registry and exits 0
- **AND** the command exits 1 when the image has no digest and names `latest` or no tag

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 999, with `runAsNonRoot`, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be `emptyDir` volumes only, and `/dev/shm` SHALL be a memory volume of 1 Gi.

#### Scenario: A control is missing
- **WHEN** `kubectl -n devops rollout status deployment/crawl4ai` completes in namespace `devops`, which enforces Pod Security `restricted`, and a person runs `kubectl -n devops get pods -l app.kubernetes.io/name=crawl4ai -o jsonpath='{..runAsUser} {..readOnlyRootFilesystem} {..volumeMounts[*].mountPath}'`
- **THEN** the API server admitted the pod, the pod runs as user 999 with a read-only root file system, and no mount path is `/var/run/secrets/kubernetes.io/serviceaccount`
- **AND** `uv run devops k8s lint k8s/devops/crawl4ai` reports no finding

### Requirement: The pod holds the token and no switch that widens its reach
The environment of the container SHALL hold `CRAWL4AI_API_TOKEN` from the key `CRAWL4AI_API_TOKEN` of Secret `crawl4ai`, and `GUNICORN_BIND` set to `0.0.0.0:11235`. It SHALL set none of `CRAWL4AI_ALLOW_INTERNAL_URLS`, `CRAWL4AI_HOOKS_ENABLED` and `CRAWL4AI_EXECUTE_JS_ENABLED`, and SHALL load no Secret with `envFrom`.

#### Scenario: A switch is set
- **WHEN** a person runs `uv run devops k8s crawl4ai-check`
- **THEN** each route refuses each internal target, each route refuses a request without the token, and the command exits 0

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

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/crawl4ai/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/crawl4ai/`

### Requirement: The scan of the third-party image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan, in its matrix entry `crawl4ai`, the image of the Deployment with `.github/actions/image-scan` at exit code 0 under the category `trivy-image-crawl4ai`, and SHALL exit 0 whatever it finds. The workflow SHALL run only for a pull request that changes `k8s/devops/crawl4ai/deployment.yaml`, the workflow file or the action.

#### Scenario: The scan fails the job
- **WHEN** a pull request changes `k8s/devops/crawl4ai/deployment.yaml`, and a person runs `uv run devops gh pr checks <number>`
- **THEN** the check `Third-Party Image Scan (crawl4ai)` passes also when Trivy reports a finding
- **AND** `uv run devops ci --check --only actionlint,zizmor` passes on the workflow

#### Scenario: A pull request that does not change the Deployment
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
