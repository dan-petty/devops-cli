## MODIFIED Requirements

### Requirement: The Deployment pins the image by release and digest
Deployment `searxng` in `k8s/devops/searxng/deployment.yaml` SHALL run one container whose image is `docker.io/searxng/searxng:<date-tag>@sha256:<digest>`, with one replica.

#### Scenario: The image names a tag only
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops`
- **THEN** the command resolves the image of Deployment `searxng` by its digest at the registry and exits 0
- **AND** the command exits 1 when the image has no digest and names `latest` or no tag

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 977 and group 977, with `runAsNonRoot`, `fsGroup` 977, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be a ConfigMap and `emptyDir` volumes only, and its only writable paths SHALL be `/tmp` and `/var/cache/searxng`.

#### Scenario: A control is missing
- **WHEN** `kubectl -n devops rollout status deployment/searxng` completes in namespace `devops`, which enforces Pod Security `restricted`, and a person runs `kubectl -n devops get pods -l app.kubernetes.io/name=searxng -o jsonpath='{..runAsUser} {..runAsGroup} {..readOnlyRootFilesystem} {..volumeMounts[*].mountPath}'`
- **THEN** the API server admitted the pod, the pod runs as user 977 and group 977 with a read-only root file system, and no mount path is `/var/run/secrets/kubernetes.io/serviceaccount`
- **AND** `uv run devops k8s lint k8s/devops/searxng` reports no finding

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

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `searxng-perimeter` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 8080. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `searxng-clients` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` and `kubectl get ingress --all-namespaces`
- **THEN** the connect of the throwaway pod that is no client of the service to port 8080 is `blocked`, and no Ingress has the Service `searxng` as a backend
- **AND** `uv run devops ci --check --only k8s` passes only when the Service pod and the stage Job pod reach the service and the runner Job pod does not

### Requirement: The pod reaches DNS and public HTTPS only
NetworkPolicy `searxng-perimeter` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter` removes. `devops-default-perimeter` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** the connects of the throwaway pod with the label of `searxng` to the metadata address and to a private ClusterIP are `blocked`, and the search rows return hits from the public engines

### Requirement: Granian replaces a worker before the memory limit
The Deployment SHALL set `GRANIAN_WORKERS_MAX_RSS` to `512`, and its memory limit SHALL hold a worker at that value and the new worker that Granian starts in its place: a request of 256 Mi and a limit of 1 Gi.

#### Scenario: A worker that grows
- **WHEN** a person runs `uv run devops prometheus query 'kube_pod_container_status_last_terminated_reason{namespace="devops",container="searxng",reason="OOMKilled"}'`
- **THEN** the query returns no series, because Granian replaces a worker that grows past 512 MiB before the container reaches its limit

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`.

#### Scenario: A suspended engine is kept
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** no reply holds a hit of an engine that must stay off, no `unresponsive_engines` list names one, and the command exits 0

## REMOVED Requirements

### Requirement: The settings keep no engine that never answers
**Reason**: The requirement compares the settings with the names of a test fixture, and only a test that reads both files can check it. No live check tells an engine that never answers from an engine that is slow once (#6083).
**Migration**: The requirement "The settings keep only keyless engines" names each kept engine, and `uv run devops k8s searxng-check` checks the hits of each kept category on the cluster.

### Requirement: The cluster document lists the kept engines
**Reason**: The requirement restates the list of the settings in a document, and only a test that reads both files can check it (#6083).
**Migration**: The requirement "The settings keep only keyless engines" holds the list.

### Requirement: The ConfigMap explains the two log lines of the start
**Reason**: The requirement restates the text of a comment in a manifest, and only a test that reads the file can check it (#6083).
**Migration**: None. The comment stays in `k8s/devops/searxng/configmap.yaml`.
