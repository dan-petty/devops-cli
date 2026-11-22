## ADDED Requirements

### Requirement: The settings hold an OpenMetrics password placeholder
The `searxng-settings` ConfigMap SHALL set `general.open_metrics` to the placeholder `${SEARXNG_METRICS_PASSWORD}`, SHALL hold no password, and SHALL add no retry key.

#### Scenario: The k8s check accepts the placeholder settings
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/devops/searxng/configmap.yaml`
- **THEN** the check exits 0, reports no error for that ConfigMap, and the settings hold no password and no retry key

### Requirement: The pod renders its settings at start
The SearXNG Deployment SHALL render `/etc/searxng/settings.yml` at pod start from the `searxng-settings` ConfigMap and the `password` key of Secret `searxng-metrics-auth` into the `settings-rendered` `emptyDir`, and SHALL mount that rendered file in place of the ConfigMap file.

#### Scenario: The live check answers after the rollout
- **WHEN** `uv run devops k8s searxng-check` runs after the rollout of `k8s/devops/searxng/deployment.yaml`
- **THEN** the check exits 0 and its `general` row holds at least one hit

### Requirement: A ServiceMonitor scrapes the engine metrics
A ServiceMonitor SHALL scrape `/metrics` of Service `searxng` on its port `http` every 15 s, with basic auth from the `username` and `password` keys of Secret `searxng-metrics-auth`, and `PRODUCT_POST_HELM_BY_STACK` of the `devops` stack SHALL list it.

#### Scenario: The k8s check and the deploy dry run hold the new ServiceMonitor
- **WHEN** `uv run devops ci --check --only k8s` and `uv run devops k8s deploy-stack --stack devops --dry-run` run on the branch that creates `k8s/devops/searxng/servicemonitor.yaml`
- **THEN** the check exits 0, reports no error for the monitor, and the dry run lists it after the Helm releases

## MODIFIED Requirements

### Requirement: Only the roadmap Service calls the pod
NetworkPolicy `searxng-perimeter-ingress` SHALL admit ingress to the pod only from the pods labeled `app.kubernetes.io/name: roadmap-service` or `app.kubernetes.io/component: roadmap-stage`, on TCP 8080, and from the pods of namespace `monitoring`, on TCP 8080, for the metrics scrape. No Ingress, Traefik route or tunnel entry SHALL name the service. No NetworkPolicy of namespace `devops` but `searxng-clients` SHALL allow egress to port 8080.

#### Scenario: Another pod may call the service
- **WHEN** a person runs `uv run devops k8s searxng-check` and `kubectl get ingress --all-namespaces`
- **THEN** the connect of the throwaway pod that is no client of the service to port 8080 is `blocked`, no Ingress has the Service `searxng` as a backend, and `uv run devops ci --check --only k8s` passes only when the Service pod and the stage Job pod reach the service and the runner Job pod does not

#### Scenario: The monitoring namespace reaches the scrape port
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/devops/searxng/networkpolicy.yaml`
- **THEN** the check exits 0, the policy admits namespace `monitoring` on TCP 8080, and the runner Job pod still reaches no SearXNG port

### Requirement: The pod meets Pod Security restricted
The pod SHALL run as the numeric user 977 and group 977, with `runAsNonRoot`, `fsGroup` 977, the `RuntimeDefault` seccomp profile, no service account token, no privilege escalation, all capabilities dropped and a read-only root file system. Its volumes SHALL be a ConfigMap and `emptyDir` volumes only, and its only writable paths SHALL be `/tmp`, `/var/cache/searxng` and the `settings-rendered` `emptyDir`, which only the init container writes.

#### Scenario: A control is missing
- **WHEN** `kubectl -n devops rollout status deployment/searxng` completes in namespace `devops`, which enforces Pod Security `restricted`, and a person runs `kubectl -n devops get pods -l app.kubernetes.io/name=searxng -o jsonpath='{..runAsUser} {..runAsGroup} {..readOnlyRootFilesystem} {..volumeMounts[*].mountPath}'`
- **THEN** the API server admitted the pod, the pod runs as user 977 and group 977 with a read-only root file system, no mount path is `/var/run/secrets/kubernetes.io/serviceaccount`, and `uv run devops k8s lint k8s/devops/searxng` reports no finding

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/searxng/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `PRODUCT_MANIFESTS_BY_STACK["devops"]`, or in `PRODUCT_POST_HELM_BY_STACK["devops"]` when it needs the `monitoring.coreos.com` CRDs; `k8s/devops/searxng/servicemonitor.yaml` SHALL be in the second.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/searxng/`
