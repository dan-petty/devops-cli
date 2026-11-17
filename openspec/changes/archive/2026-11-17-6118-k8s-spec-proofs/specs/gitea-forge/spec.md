## REMOVED Requirements

### Requirement: Argo CD installs the pinned Gitea chart
**Reason**: Its scenario named a test that reads `k8s/argocd/apps/gitea.yaml`, and the requirement restated the chart version that Renovate updates. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check and no version (#6083).
**Migration**: The requirement "Argo CD installs the Gitea chart" holds the same rule.

### Requirement: Argo CD applies the Gitea perimeter
**Reason**: Its scenario named a test that reads the Application and the kustomization. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with live checks (#6083).
**Migration**: The requirement "Argo CD applies the Gitea perimeter from git" holds the same rule.

### Requirement: The projects admit Gitea
**Reason**: Its scenario named a test that reads `k8s/argocd/apps/projects.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "The homelab projects admit the Gitea sources and namespace" holds the same rule.

### Requirement: Namespace gitea enforces restricted Pod Security and keeps its data
**Reason**: Its scenario named a test that reads `k8s/namespaces.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check and the `k8s` row (#6083).
**Migration**: The requirement "The gitea namespace refuses a privileged pod and keeps its data" holds the same rule.

### Requirement: Gitea runs one pod on SQLite in WAL mode
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Gitea runs one pod on a SQLite database in WAL mode" holds the same rule.

### Requirement: Gitea keeps its data on a worker node
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Gitea keeps its data on a kept claim on a worker node" holds the same rule.

### Requirement: Gitea is a locked forge with no SSH and no egress need
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Gitea is a closed forge with no SSH and no egress need" holds the same rule.

### Requirement: Gitea runs rootless and non-root with bounded resources
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`, and the requirement restated the image tag that Renovate updates. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check and no tag (#6083).
**Migration**: The requirement "Gitea runs rootless as a non-root user with bounded resources" holds the same rule.

### Requirement: Gitea's values name no domain, and its public URLs come from each request
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Gitea builds its public URLs from each request" holds the same rule.

### Requirement: The git host routes through Traefik to the Gitea HTTP Service
**Reason**: Its scenario named a test that reads `k8s/ingress/ingress-routes.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check and the `k8s` row (#6083).
**Migration**: The requirement "Traefik routes the git host to the Gitea HTTP Service" holds the same rule.

### Requirement: The Gitea perimeter admits only Gitea's HTTP port
**Reason**: Its scenario named a test that reads `k8s/gitea/networkpolicy.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with live probes (#6083).
**Migration**: The requirement "The Gitea perimeter admits only the HTTP port of Gitea" holds the same rule.

## ADDED Requirements

### Requirement: Argo CD installs the Gitea chart
Application `gitea` SHALL install chart `gitea` from `https://dl.gitea.com/charts/` at the version that the Application pins, into namespace `gitea`, with the one value file `$values/k8s/gitea/values.yaml` read from `https://github.com/dan-petty/devops-cli` at `main`. It SHALL be in project `homelab`, with the finalizer, automated prune and self-heal, and the retry of the other leaf Applications.

#### Scenario: The Gitea chart Application syncs
- **WHEN** a person runs `kubectl -n argocd get application gitea`
- **THEN** the Application is `Synced` and `Healthy`, in project `homelab`, with namespace `gitea` as its destination

### Requirement: Argo CD applies the Gitea perimeter from git
Application `gitea-manifests` SHALL render path `k8s/gitea` from `https://github.com/dan-petty/devops-cli` at `main` into namespace `gitea`, in project `homelab` with the sync policy of the other leaf Applications. The kustomization `k8s/gitea/kustomization.yaml` SHALL list only `networkpolicy.yaml`.

#### Scenario: The Gitea manifests Application syncs
- **WHEN** a person runs `kubectl -n argocd get application gitea-manifests` and `kubectl -n gitea get networkpolicy`
- **THEN** the Application is `Synced` and `Healthy`, and the namespace holds the Gitea perimeter
- **AND** `uv run devops ci --check --only k8s` passes only when one Application renders each object of `k8s/gitea`

### Requirement: The homelab projects admit the Gitea sources and namespace
The AppProject `homelab` SHALL admit `https://dl.gitea.com/charts/` and namespace `gitea`, and SHALL ignore Secret `gitea-admin` as an orphan. The AppProject `homelab-system` SHALL admit namespace `gitea`.

#### Scenario: The Gitea Applications are valid
- **WHEN** a person runs `kubectl -n argocd get applications gitea gitea-manifests -o jsonpath='{..conditions[*].type}'`
- **THEN** neither Application has the condition `InvalidSpecError`, and neither has the condition `OrphanedResourceWarning` for Secret `gitea-admin`

### Requirement: The gitea namespace refuses a privileged pod and keeps its data
The root kustomization's `k8s/namespaces.yaml` SHALL declare namespace `gitea` with Pod Security `restricted` for enforce, warn and audit, and with `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.

#### Scenario: A privileged pod in namespace gitea
- **WHEN** a person runs `kubectl -n gitea run probe --image=busybox:1.37.0 --privileged --dry-run=server`
- **THEN** the API server refuses the pod for the `restricted` level of Pod Security
- **AND** `uv run devops ci --check --only k8s` passes only when the Namespace `gitea` has `Prune=false` and `Delete=false`

### Requirement: Gitea runs one pod on a SQLite database in WAL mode
The values SHALL disable `postgresql`, `postgresql-ha`, `valkey` and `valkey-cluster`, run one replica with strategy `Recreate`, set `database` to `sqlite3` with journal mode `WAL`, keep sessions in the database, use the `memory` cache and the `level` queue, and leave `APP_DATA_PATH` and `repository.ROOT` to the chart.

#### Scenario: The database and the pods
- **WHEN** a person runs `kubectl -n gitea get pods,statefulsets` and `kubectl -n gitea get deployment gitea -o jsonpath='{.spec.replicas} {.spec.strategy.type}'`
- **THEN** one Gitea pod runs, no PostgreSQL or Valkey pod or StatefulSet exists, and the Deployment prints `1 Recreate`

### Requirement: Gitea keeps its data on a kept claim on a worker node
Persistence SHALL be on, with claim `gitea-shared-storage` of 10Gi in storage class `local-path`, annotated `helm.sh/resource-policy: keep` and `argocd.argoproj.io/sync-options: Prune=false,Delete=false`. The pod SHALL require a node without the label `node-role.kubernetes.io/control-plane`.

#### Scenario: The claim and the node
- **WHEN** a person runs `kubectl -n gitea get pvc gitea-shared-storage` and `kubectl -n gitea get pods -o wide`
- **THEN** the claim is `Bound` in storage class `local-path`, and the Gitea pod runs on a node with no label `node-role.kubernetes.io/control-plane`

### Requirement: Gitea is a closed forge with no SSH and no egress need
The values SHALL disable registration, require a sign-in to view, make new repositories private, keep push-to-create off for users and organizations, disable migrations, mirrors and Actions, disable the `update_checker` cron job, set `OFFLINE_MODE`, and turn SSH off (`DISABLE_SSH: true`, `START_SSH_SERVER: false`).

#### Scenario: A visitor with no account
- **WHEN** a person runs `kubectl -n gitea port-forward svc/gitea-http 3000:3000` and sends `GET /user/sign_up` and `GET /explore/repos` to the local port with no session
- **THEN** the sign-up page says that registration is off, and the explore page sends the visitor to `/user/login`
- **AND** `kubectl -n gitea get services` lists no port 22 and no port 2222

### Requirement: Gitea runs rootless as a non-root user with bounded resources
The values SHALL run a release tag of the rootless image, run the pod as non-root user and group 1000 with fsGroup 1000 and the `RuntimeDefault` seccomp profile, run each container with no privilege escalation, a read-only root filesystem and all capabilities dropped, request 100m CPU and 256Mi and limit 1 CPU and 1Gi, and render no chart test pod.

#### Scenario: The running Gitea pod
- **WHEN** `kubectl -n gitea rollout status deployment/gitea` completes in namespace `gitea`, which enforces Pod Security `restricted`, and a person runs `kubectl -n gitea get pods -l app.kubernetes.io/name=gitea -o jsonpath='{..runAsUser} {..runAsGroup} {..readOnlyRootFilesystem}'`
- **THEN** the API server admitted the pod, and the pod runs as user 1000 and group 1000 with a read-only root file system
- **AND** `kubectl -n gitea get pods` lists no chart test pod

### Requirement: Gitea builds its public URLs from each request
The values SHALL set `ROOT_URL` to `http://gitea-http.gitea.svc.cluster.local:3000/`, `DOMAIN` to `gitea-http.gitea.svc.cluster.local` and `PUBLIC_URL_DETECTION` to `auto`, disable the chart's Ingress, keep the `http` Service as `ClusterIP` on port 3000, and hold no key or value that contains the placeholder domain.

#### Scenario: Two hosts give two URLs
- **WHEN** a person sends `GET /` to Gitea once through `kubectl -n gitea port-forward svc/gitea-http 3000:3000` and once through the git host
- **THEN** the links of the first page name `localhost:3000`, the links of the second page name the git host, and no link names `example.com`
- **AND** `kubectl -n gitea get service gitea-http` shows type `ClusterIP` on port 3000

### Requirement: Traefik routes the git host to the Gitea HTTP Service
`k8s/ingress/ingress-routes.yaml` SHALL hold Ingress `gitea-ingress` in namespace `gitea` with class `traefik`, the entrypoint annotation `web`, one rule for host `git.example.com` with path `/` of type `Prefix` to Service `gitea-http` port 3000, and no `tls` block.

#### Scenario: The Gitea Ingress
- **WHEN** a person runs `kubectl -n gitea get ingress`
- **THEN** the namespace holds one Ingress, `gitea-ingress`, of class `traefik`, with the git host of the configured domain and the backend `gitea-http` on port 3000
- **AND** `uv run devops ci --check --only k8s` passes only when the host overrides of the Application change every host that it renders

### Requirement: The Gitea perimeter admits only the HTTP port of Gitea
`k8s/gitea/networkpolicy.yaml` SHALL select every pod in namespace `gitea`, admit TCP 3000 only from Traefik's pods in `kube-system`, the `argocd-repo-server` pods in `argocd` and the namespace's own pods, admit no address range and no SSH port, and allow egress only to CoreDNS on port 53 and to the namespace's own pods.

#### Scenario: The Gitea perimeter peers
- **WHEN** a throwaway pod in namespace `default` and a throwaway pod in namespace `gitea` each run `nc -w 3 gitea-http.gitea.svc.cluster.local 3000`, and the pod in namespace `gitea` also runs `nc -w 3 example.com 443`, each started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect from `default` times out, the connect from `gitea` succeeds, and the connect to `example.com` times out
- **AND** the git host answers through Traefik
