# searxng-service Specification

## Purpose
How the SearXNG search service runs in namespace `devops`: its pod controls, the pinned image, the engines it keeps, who may call it and where it may connect. The service has no limiter and no login, so its network perimeter is the access control, and its engine list keeps out the engines that need a key or that their upstream sites suspended.

## Requirements

### Requirement: The Deployment pins the image by release and digest
Deployment `searxng` in `k8s/devops/searxng/deployment.yaml` SHALL run one container whose image is `docker.io/searxng/searxng:<date-tag>@sha256:<digest>`, with one replica.

#### Scenario: The image names a tag only
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops`
- **THEN** the command resolves the image of Deployment `searxng` by its digest at the registry and exits 0
- **AND** the command exits 1 when the image has no digest and names `latest` or no tag

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 977 and group 977, with `runAsNonRoot`, `fsGroup` 977, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be a ConfigMap and `emptyDir` volumes only, and its only writable paths SHALL be `/tmp`, `/var/cache/searxng` and the `settings-rendered` `emptyDir`, which only the init container writes.

#### Scenario: A control is missing
- **WHEN** `kubectl -n devops rollout status deployment/searxng` completes in namespace `devops`, which enforces Pod Security `restricted`, and a person runs `kubectl -n devops get pods -l app.kubernetes.io/name=searxng -o jsonpath='{..runAsUser} {..runAsGroup} {..readOnlyRootFilesystem} {..volumeMounts[*].mountPath}'`
- **THEN** the API server admitted the pod, the pod runs as user 977 and group 977 with a read-only root file system, no mount path is `/var/run/secrets/kubernetes.io/serviceaccount`, and `uv run devops k8s lint k8s/devops/searxng` reports no finding

### Requirement: The server secret comes from a Secret and the settings hold none
The container SHALL read `SEARXNG_SECRET` from the key `SEARXNG_SECRET` of Secret `searxng`. The cluster secret table SHALL hold the row `devops/searxng` with the keyring-only value `searxng_secret_key`, generated as 64 hex characters, and a restart of `deployment/searxng`. The settings file SHALL hold no `secret_key` and no e-mail address.

#### Scenario: A secret is in the settings
- **WHEN** a person runs `uv run devops k8s push-secrets --stack devops --dry-run` and `uv run devops scan secrets k8s/devops/searxng`
- **THEN** the dry run writes key `SEARXNG_SECRET` of Secret `devops/searxng` from keyring `searxng_secret_key` and restarts `deployment/searxng`, with no value in the output
- **AND** the secret scan reports no finding in the settings

### Requirement: The settings turn off the limiter and serve JSON
The settings SHALL set `server.limiter`, `server.public_instance` and `server.image_proxy` to false, and `search.formats` to `html` and `json`.

#### Scenario: JSON is off
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** the service answers each of the six search rows, all sent with `format=json`, with no HTTP 403 and no HTTP 429, and the command exits 0

### Requirement: Only the roadmap Service and stage Jobs call the pod
NetworkPolicy `searxng-perimeter-ingress` SHALL admit TCP 8080 ingress only from the roadmap-service pods (`app.kubernetes.io/name: roadmap-service`), the stage Job pods (`app.kubernetes.io/component: roadmap-stage`), and namespace `monitoring`. No Ingress, Traefik route, or tunnel entry SHALL name the service. Only `searxng-clients` and `searxng-stage-clients` in namespace `devops` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` and `kubectl get ingress --all-namespaces`
- **THEN** the connect of the throwaway pod that is no client of the service to port 8080 is `blocked`, no Ingress has the Service `searxng` as a backend, and `uv run devops ci --check --only k8s` passes only when the roadmap-service pods (via `searxng-clients`) and the stage Job pods (via `searxng-stage-clients`) reach the service on port 8080 and the runner Job pod does not

#### Scenario: The monitoring namespace reaches the scrape port
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/devops/searxng/networkpolicy.yaml`
- **THEN** the check exits 0, the policy admits namespace `monitoring` on TCP 8080, and the runner Job pod still reaches no SearXNG port

### Requirement: The pod reaches DNS and public HTTPS only
NetworkPolicy `searxng-perimeter-egress` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter-egress` removes. `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** the connects of the throwaway pod with the label of `searxng` to the metadata address and to a private ClusterIP are `blocked`, and the search rows return hits from the public engines

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/searxng/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `PRODUCT_MANIFESTS_BY_STACK["devops"]`, or in `PRODUCT_POST_HELM_BY_STACK["devops"]` when it needs the `monitoring.coreos.com` CRDs; `k8s/devops/searxng/servicemonitor.yaml` SHALL be in the second.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/searxng/`

### Requirement: Granian replaces a worker before the memory limit
The Deployment SHALL set `GRANIAN_WORKERS_MAX_RSS` to `512`, and its memory limit SHALL hold a worker at that value and the new worker that Granian starts in its place: a request of 256 Mi and a limit of 1 Gi.

#### Scenario: A worker that grows
- **WHEN** a person runs `uv run devops prometheus query 'kube_pod_container_status_last_terminated_reason{namespace="devops",container="searxng",reason="OOMKilled"}'`
- **THEN** the query returns no series, because Granian replaces a worker that grows past 512 MiB before the container reaches its limit

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek`, `qwant`, `stackoverflow`, `askubuntu` and `superuser`.

#### Scenario: A suspended engine is kept
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** no reply holds a hit of an engine that must stay off, no `unresponsive_engines` list names one, and the command exits 0

#### Scenario: The settings render with the six kept engines
- **WHEN** a person runs `uv run devops ci --check --only k8s` over `k8s/devops/searxng/configmap.yaml`
- **THEN** the render succeeds

#### Scenario: The general category holds a hit
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster after the rollout of `k8s/devops/searxng/configmap.yaml`
- **THEN** the row of the general category holds at least one hit, and the command exits 0

### Requirement: A SearXNG bump updates like any other image
No test SHALL compare a file or a constant with the pinned SearXNG image. The Renovate rule of the image SHALL give the pull request a note that names `devops k8s searxng-check` and names no age of the tag.

#### Scenario: A bump of the image
- **WHEN** Renovate opens a pull request that moves the SearXNG image
- **THEN** its text names `devops k8s searxng-check`, and no test fails only because the image moved

### Requirement: The settings hold an OpenMetrics password placeholder
The `searxng-settings` ConfigMap SHALL set `general.open_metrics` to the placeholder `${SEARXNG_METRICS_PASSWORD}`, SHALL hold no password, and SHALL add no retry key.

#### Scenario: The k8s check accepts the placeholder settings
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/devops/searxng/configmap.yaml`
- **THEN** the check exits 0, reports no error for that ConfigMap, and the settings hold no password and no retry key

### Requirement: The pod renders its settings at start
The SearXNG Deployment SHALL render `/etc/searxng/settings.yml` at pod start from the `searxng-settings` ConfigMap and the `password` key of Secret `searxng-metrics-auth` into the `settings-rendered` `emptyDir`, and SHALL mount that rendered file in place of the ConfigMap file.

#### Scenario: The rendered settings hold the password of the Secret
- **WHEN** `uv run devops ci --check --only k8s` runs `render-settings` with a password that holds `&`, `\` and `|`
- **THEN** the init container exits 0, the rendered `general.open_metrics` is that password, and it logs nothing

#### Scenario: The live check answers after the rollout
- **WHEN** `uv run devops k8s searxng-check` runs after the rollout of `k8s/devops/searxng/deployment.yaml`
- **THEN** the check exits 0 and its `general` row holds at least one hit

### Requirement: A ServiceMonitor scrapes the engine metrics
A ServiceMonitor SHALL scrape `/metrics` of Service `searxng` on its port `http` every 15 s, with basic auth from the `username` and `password` keys of Secret `searxng-metrics-auth`, and `PRODUCT_POST_HELM_BY_STACK` of the `devops` stack SHALL list it.

#### Scenario: The k8s check and the deploy dry run hold the new ServiceMonitor
- **WHEN** `uv run devops ci --check --only k8s` and `uv run devops k8s deploy-stack --stack devops --dry-run` run on the branch that creates `k8s/devops/searxng/servicemonitor.yaml`
- **THEN** the check exits 0, reports no error for the monitor, and the dry run lists it after the Helm releases

### Requirement: The pod starts without the metrics Secret
The reference of the init container `render-settings` to Secret `searxng-metrics-auth` SHALL be optional. When the Secret or its key `password` is missing, `render-settings` SHALL write an empty `general.open_metrics`, which turns the OpenMetrics endpoint off, SHALL log one line that names Secret `devops/searxng-metrics-auth`, and SHALL exit 0.

#### Scenario: The pod starts without the metrics Secret
- **WHEN** `uv run devops ci --check --only k8s` runs `render-settings` with no Secret `searxng-metrics-auth`
- **THEN** the init container starts and exits 0, the rendered settings hold an empty `general.open_metrics`, and its log is one line that names `devops/searxng-metrics-auth`
