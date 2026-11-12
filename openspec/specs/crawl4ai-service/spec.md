# crawl4ai-service Specification

## Purpose
How the Crawl4AI page-text service runs in namespace `devops`: its pod controls, the pinned image, who may call it, and where it may connect. The service renders pages that a model chose, so its network perimeter is the main control against a request to an internal address.

## Requirements

### Requirement: The Deployment pins the image by release and digest
Deployment `crawl4ai` in `k8s/devops/crawl4ai/deployment.yaml` SHALL run one container whose image is `unclecode/crawl4ai:<release>@sha256:<digest>`, with one replica and the `Recreate` strategy.

#### Scenario: The image names a tag only
- **WHEN** a test reads the image of the container of Deployment `crawl4ai`
- **THEN** the image holds a release tag and a 64-digit digest, and does not name `latest`

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 999, with `runAsNonRoot`, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be `emptyDir` volumes only, and `/dev/shm` SHALL be a memory volume of 1 Gi.

#### Scenario: A control is missing
- **WHEN** a test reads the pod spec of Deployment `crawl4ai`
- **THEN** each control above is set, the six upstream tmpfs paths are mounted from `emptyDir` volumes, and no volume is of another kind

### Requirement: The pod holds the token and no switch that widens its reach
The environment of the container SHALL hold `CRAWL4AI_API_TOKEN` from the key `CRAWL4AI_API_TOKEN` of Secret `crawl4ai`, and `GUNICORN_BIND` set to `0.0.0.0:11235`. It SHALL set none of `CRAWL4AI_ALLOW_INTERNAL_URLS`, `CRAWL4AI_HOOKS_ENABLED` and `CRAWL4AI_EXECUTE_JS_ENABLED`, and SHALL load no Secret with `envFrom`.

#### Scenario: A switch is set
- **WHEN** a test reads the environment of the container
- **THEN** the names are `CRAWL4AI_API_TOKEN` and `GUNICORN_BIND` and no other

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `crawl4ai-perimeter` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 11235. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `roadmap-service-to-crawl4ai` SHALL allow egress to port 11235.

#### Scenario: Another pod may call the service
- **WHEN** a test reads the NetworkPolicies of namespace `devops` and the routes under `k8s/`
- **THEN** one ingress rule with one pod selector peer reaches the pod, and no other policy sends to port 11235

### Requirement: The pod reaches DNS and public web pages only
NetworkPolicy `crawl4ai-perimeter` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 80 and 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter` removes. `devops-default-perimeter` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a test reads the egress rules of `crawl4ai-perimeter` and the selector of `devops-default-perimeter`
- **THEN** the removed ranges equal those of the default perimeter, and the default perimeter skips `crawl4ai`

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/crawl4ai/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** a test compares the files of the folder with the three lists
- **THEN** the lists name the same files

### Requirement: The scan of the third-party image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan the image of the Deployment with Trivy at the version that `tools.lock` pins and SHALL exit 0 whatever it finds. The workflow SHALL run only for a pull request that changes `k8s/devops/crawl4ai/deployment.yaml` or the workflow file.

#### Scenario: The scan fails the job
- **WHEN** a test reads the workflow
- **THEN** the exit code of the Trivy step is 0 and the `paths` filter of the `pull_request` trigger names the Deployment

#### Scenario: A pull request that does not change the Deployment
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
