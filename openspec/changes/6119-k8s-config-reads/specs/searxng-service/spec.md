## MODIFIED Requirements

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 977 and group 977, with `runAsNonRoot`, `fsGroup` 977, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be a ConfigMap and `emptyDir` volumes only, and its only writable paths SHALL be `/tmp` and `/var/cache/searxng`.

#### Scenario: A control is missing
- **WHEN** `uv run devops k8s lint k8s/devops/searxng` runs kube-linter on the manifests, and the Deployment rolls out
- **THEN** kube-linter reports no finding for the pod, and the API server admits the pod in its namespace, which enforces Pod Security `restricted`

### Requirement: The server secret comes from a Secret and the settings hold none
The container SHALL read `SEARXNG_SECRET` from the key `SEARXNG_SECRET` of Secret `searxng`. The cluster secret table SHALL hold the row `devops/searxng` with the keyring-only value `searxng_secret_key`, generated as 64 hex characters, and a restart of `deployment/searxng`. The settings file SHALL hold no `secret_key` and no e-mail address.

#### Scenario: A secret is in the settings
- **WHEN** a person runs `kubectl -n devops get deployment searxng -o yaml` and `kubectl -n devops get configmap searxng-settings -o yaml` on the cluster
- **THEN** the variable comes from Secret `searxng`, and the settings hold no `secret_key` and no e-mail address

### Requirement: The settings turn off the limiter and serve JSON
The settings SHALL set `server.limiter`, `server.public_instance` and `server.image_proxy` to false, and `search.formats` to `html` and `json`.

#### Scenario: JSON is off
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster
- **THEN** no reply is HTTP 403 or HTTP 429, so `json` is in `search.formats` and the limiter refuses no request

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `searxng-perimeter` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 8080. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `searxng-clients` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster
- **THEN** the throwaway pod that is not a client of the service does not reach port 8080

### Requirement: The pod reaches DNS and public HTTPS only
NetworkPolicy `searxng-perimeter` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter` removes. `devops-default-perimeter` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster
- **THEN** the throwaway pod with the label of the service reaches neither the metadata address nor a private ClusterIP

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/searxng/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/searxng/`

### Requirement: Granian replaces a worker before the memory limit
The Deployment SHALL set `GRANIAN_WORKERS_MAX_RSS` to `512`, and its memory limit SHALL hold a worker at that value and the new worker that Granian starts in its place: a request of 256 Mi and a limit of 1 Gi.

#### Scenario: A worker that grows
- **WHEN** a person runs `kubectl -n devops get deployment searxng -o yaml` on the cluster
- **THEN** its environment holds `GRANIAN_WORKERS_MAX_RSS` with the value `512`, and its memory request is `256Mi` and its limit `1Gi`

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`.

#### Scenario: A suspended engine is kept
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster
- **THEN** no forbidden engine shows in `results` or in `unresponsive_engines`

## REMOVED Requirements

### Requirement: The settings keep no engine that never answers
**Reason**: The list of engines that never answer was test data of a test that read the settings, and #6119 deletes it (#6060).
**Migration**: `uv run devops k8s searxng-check` fails a category with no hit, and `docs/CLUSTER.md` records why `pypi` is not kept.

### Requirement: The cluster document lists the kept engines
**Reason**: No test reads the settings for their values (#6060), so no test compares them with the document.
**Migration**: The review of a change of `keep_only` changes the sentence "The engines." of `docs/CLUSTER.md` in the same pull request.
