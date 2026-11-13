# searxng-service Specification

## Purpose
How the SearXNG search service runs in namespace `devops`: its pod controls, the pinned image, the engines it keeps, who may call it and where it may connect. The service has no limiter and no login, so its network perimeter is the access control, and its engine list keeps out the engines that need a key or that their upstream sites suspended.

## Requirements

### Requirement: The Deployment pins the image by release and digest
Deployment `searxng` in `k8s/devops/searxng/deployment.yaml` SHALL run one container whose image is `docker.io/searxng/searxng:<date-tag>@sha256:<digest>`, with one replica.

#### Scenario: The image names a tag only
- **WHEN** a test reads the image of the container of Deployment `searxng`
- **THEN** the image holds a date tag with a commit and a 64-digit digest, and does not name `latest`

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 977 and group 977, with `runAsNonRoot`, `fsGroup` 977, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be a ConfigMap and `emptyDir` volumes only, and its only writable paths SHALL be `/tmp` and `/var/cache/searxng`.

#### Scenario: A control is missing
- **WHEN** a test reads the pod spec of Deployment `searxng`
- **THEN** each control above is set and no volume is of another kind

### Requirement: The server secret comes from a Secret and the settings hold none
The container SHALL read `SEARXNG_SECRET` from the key `SEARXNG_SECRET` of Secret `searxng`. The cluster secret table SHALL hold the row `devops/searxng` with the keyring-only value `searxng_secret_key`, generated as 64 hex characters, and a restart of `deployment/searxng`. The settings file SHALL hold no `secret_key` and no e-mail address.

#### Scenario: A secret is in the settings
- **WHEN** a test reads the environment of the container, the table row and the text of the ConfigMap
- **THEN** the variable comes from the Secret, the row exists, and the file has no `secret_key`

### Requirement: The settings turn off the limiter and serve JSON
The settings SHALL set `server.limiter`, `server.public_instance` and `server.image_proxy` to false, and `search.formats` to `html` and `json`.

#### Scenario: JSON is off
- **WHEN** a test reads the settings of ConfigMap `searxng-settings`
- **THEN** the three server switches are false and `json` is in `search.formats`

### Requirement: The settings keep only engines that need no key
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`. Every kept name SHALL be an engine name in the default settings of the pinned image.

#### Scenario: A suspended engine is kept
- **WHEN** a test reads `keep_only` and the engine names file of the pinned image
- **THEN** no kept name is a forbidden engine, and every kept name is in the names file

#### Scenario: A bump leaves the names file behind
- **WHEN** a test compares the tag in the first line of the names file with the tag of the Deployment
- **THEN** the tags are the same

### Requirement: The settings keep no engine that never answers
The settings SHALL keep no engine that `tests/fixtures/searxng/engines_that_never_answer.txt` lists. Each line of that file SHALL give a date and a reason.

#### Scenario: An engine that never answers is kept
- **WHEN** a test reads `keep_only` and `tests/fixtures/searxng/engines_that_never_answer.txt`
- **THEN** no kept name is in that file, the first name in that file is `pypi`, each line has a date and a reason, and every name is an engine of the default settings

### Requirement: The cluster document lists the kept engines
The list of engines in `docs/CLUSTER.md` SHALL name the same engines as `keep_only`.

#### Scenario: The README lists other engines than the settings
- **WHEN** a test reads the sentence "The engines." of `docs/CLUSTER.md` and `keep_only`
- **THEN** the names in backticks in the sentence equal the names in `keep_only`

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `searxng-perimeter` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service`, on TCP 8080. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `searxng-clients` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a test reads the NetworkPolicies of namespace `devops` and the routes under `k8s/`
- **THEN** one ingress rule with one pod selector peer reaches the pod, and no other policy sends to port 8080

### Requirement: The pod reaches DNS and public HTTPS only
NetworkPolicy `searxng-perimeter` SHALL allow egress to CoreDNS and to `0.0.0.0/0` on TCP 443, less the private, shared, link-local, cloud metadata and special-purpose ranges that `devops-default-perimeter` removes. `devops-default-perimeter` SHALL NOT select the pod.

#### Scenario: The pod reaches a private range
- **WHEN** a test reads the egress rules of `searxng-perimeter` and the selector of `devops-default-perimeter`
- **THEN** the removed ranges equal those of the default perimeter, and the default perimeter skips `searxng`

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/searxng/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** a test compares the files of the folder with the three lists
- **THEN** the lists name the same files

### Requirement: A bump of the image tells the person what to check
The Renovate configuration SHALL hold a rule for the image whose pull request text names the refresh of the engine names file and names no age of the tag.

#### Scenario: The note is missing
- **WHEN** a test reads `.github/renovate.json`
- **THEN** one rule matches the image, its note names the engine names file, and its note does not hold `days old`

### Requirement: The ConfigMap explains the two log lines of the start
The file `k8s/devops/searxng/configmap.yaml` SHALL hold a comment, outside the text of `settings.yml`, that names the ERROR "X-Forwarded-For nor X-Real-IP header is set!" with its source `searx/botdetection/trusted_proxies.py`, and the WARNING for a missing `limiter.toml` with its source `searx/botdetection/config.py`, and that says both are harmless with the limiter off.

#### Scenario: The comment is missing
- **WHEN** a test reads the text of `k8s/devops/searxng/configmap.yaml`
- **THEN** the text names `X-Forwarded-For`, `searx/botdetection/trusted_proxies.py`, `limiter.toml`, `searx/botdetection/config.py` and the word "harmless"

### Requirement: Granian replaces a worker before the memory limit
The Deployment SHALL set `GRANIAN_WORKERS_MAX_RSS` to `512`, and its memory limit SHALL hold a worker at that value and the new worker that Granian starts in its place: a request of 256 Mi and a limit of 1 Gi.

#### Scenario: A worker that grows
- **WHEN** a test reads the container of Deployment `searxng`
- **THEN** its environment holds `GRANIAN_WORKERS_MAX_RSS` with the value `512`, and its memory request is `256Mi` and its limit `1Gi`
