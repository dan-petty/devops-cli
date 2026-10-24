## Purpose

How the homelab runs Gitea, its internal forge and container registry: the Argo CD Applications and the deploy-stack stack that install it, its chart values, its perimeter, its git host and its admin Secret.

## ADDED Requirements

### Requirement: Argo CD installs the pinned Gitea chart
Application `gitea` SHALL install chart `gitea` at version 12.7.0 from `https://dl.gitea.com/charts/` into namespace `gitea`, with the one value file `$values/k8s/gitea/values.yaml` read from `https://github.com/dan-petty/devops-cli` at `main`. It SHALL be in project `homelab`, with the finalizer, automated prune and self-heal, and the retry of the other leaf Applications.

#### Scenario: A test reads the Gitea chart Application
- **WHEN** a test reads `k8s/argocd/apps/gitea.yaml`
- **THEN** it names the chart, the version, the value file, the project, the destination and the sync policy above

### Requirement: Argo CD applies the Gitea perimeter
Application `gitea-manifests` SHALL render path `k8s/gitea` from `https://github.com/dan-petty/devops-cli` at `main` into namespace `gitea`, in project `homelab` with the sync policy of the other leaf Applications. The kustomization `k8s/gitea/kustomization.yaml` SHALL list only `networkpolicy.yaml`.

#### Scenario: A test reads the Gitea manifests Application
- **WHEN** a test reads `k8s/argocd/apps/gitea-manifests.yaml` and `k8s/gitea/kustomization.yaml`
- **THEN** the Application names that path, project, destination and sync policy, and the kustomization lists only the perimeter

### Requirement: deploy-stack deploys Gitea as stack gitea
The deploy-stack stack `gitea` SHALL install release `gitea` (chart `gitea-charts/gitea` at 12.7.0, values `k8s/gitea/values.yaml`) from repository `https://dl.gitea.com/charts/` and apply `k8s/gitea/networkpolicy.yaml`. `--stack all` SHALL include it, it SHALL NOT be a detached stack, and its deploy SHALL set the hosts of Application `ingress`.

#### Scenario: A test reads the stack tables
- **WHEN** a test reads deploy-stack's tables
- **THEN** the stack `gitea` holds that repository, release and perimeter file

#### Scenario: A test resolves the stacks
- **WHEN** a test resolves `gitea` and `all`
- **THEN** `gitea` resolves to `["gitea"]`, `all` includes `gitea`, `gitea` is not a detached stack, and the deploy of `gitea` sets the hosts of Application `ingress`

### Requirement: The projects admit Gitea
The AppProject `homelab` SHALL admit `https://dl.gitea.com/charts/` and namespace `gitea`, and SHALL ignore Secret `gitea-admin` as an orphan. The AppProject `homelab-system` SHALL admit namespace `gitea`.

#### Scenario: A test reads the AppProjects
- **WHEN** a test reads `k8s/argocd/apps/projects.yaml`
- **THEN** the source repository, the destinations and the orphan entry above are present

### Requirement: Namespace gitea enforces restricted Pod Security and keeps its data
The root kustomization's `k8s/namespaces.yaml` SHALL declare namespace `gitea` with Pod Security `restricted` for enforce, warn and audit, and with `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.

#### Scenario: A test reads the namespaces
- **WHEN** a test reads `k8s/namespaces.yaml`
- **THEN** namespace `gitea` has those labels and that annotation

### Requirement: Gitea runs one pod on SQLite in WAL mode
The values SHALL disable `postgresql`, `postgresql-ha`, `valkey` and `valkey-cluster`, run one replica with strategy `Recreate`, set `database` to `sqlite3` with journal mode `WAL`, keep sessions in the database, use the `memory` cache and the `level` queue, and leave `APP_DATA_PATH` and `repository.ROOT` to the chart.

#### Scenario: A test reads the database and rollout values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** the bundled charts are off, and the replica count, strategy, database, session, cache and queue are those above

### Requirement: Gitea keeps its data on a worker node
Persistence SHALL be on, with claim `gitea-shared-storage` of 10Gi in storage class `local-path`, annotated `helm.sh/resource-policy: keep` and `argocd.argoproj.io/sync-options: Prune=false,Delete=false`. The pod SHALL require a node without the label `node-role.kubernetes.io/control-plane`.

#### Scenario: A test reads the storage values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** the persistence and the affinity are those above

### Requirement: Gitea is a locked forge with no SSH and no egress need
The values SHALL disable registration, require a sign-in to view, make new repositories private, keep push-to-create off for users and organizations, disable migrations, mirrors and Actions, disable the `update_checker` cron job, set `OFFLINE_MODE`, and turn SSH off (`DISABLE_SSH: true`, `START_SSH_SERVER: false`).

#### Scenario: A test reads the lock-down values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** the `service`, `repository`, `mirror`, `actions`, `cron.update_checker` and `server` keys hold those values

### Requirement: Gitea runs rootless and non-root with bounded resources
The values SHALL pin image tag `1.27.3` of the rootless image, run the pod as non-root user and group 1000 with fsGroup 1000 and the `RuntimeDefault` seccomp profile, run each container with no privilege escalation, a read-only root filesystem and all capabilities dropped, request 100m CPU and 256Mi and limit 1 CPU and 1Gi, and render no chart test pod.

#### Scenario: A test reads the image, security and resource values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** the image, pod and container security contexts, resources and `test.enabled: false` are those above

### Requirement: Gitea's values name no domain, and its public URLs come from each request
The values SHALL set `ROOT_URL` to `http://gitea-http.gitea.svc.cluster.local:3000/`, `DOMAIN` to `gitea-http.gitea.svc.cluster.local` and `PUBLIC_URL_DETECTION` to `auto`, disable the chart's Ingress, keep the `http` Service as `ClusterIP` on port 3000, and hold no key or value that contains the placeholder domain.

#### Scenario: A test reads the URL values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** the server URL keys, the Ingress and the Service are those above, and no string contains `example.com`

### Requirement: The git host routes through Traefik to the Gitea HTTP Service
`k8s/ingress/ingress-routes.yaml` SHALL hold Ingress `gitea-ingress` in namespace `gitea` with class `traefik`, the entrypoint annotation `web`, one rule for host `git.example.com` with path `/` of type `Prefix` to Service `gitea-http` port 3000, and no `tls` block.

#### Scenario: A test reads the Gitea Ingress
- **WHEN** a test reads the Ingresses in namespace `gitea` in `k8s/ingress/ingress-routes.yaml`
- **THEN** there is exactly one, and its name, annotations and spec are those above

### Requirement: The Gitea perimeter admits only Gitea's HTTP port
`k8s/gitea/networkpolicy.yaml` SHALL select every pod in namespace `gitea`, admit TCP 3000 only from Traefik's pods in `kube-system`, the `argocd-repo-server` pods in `argocd` and the namespace's own pods, admit no address range and no SSH port, and allow egress only to CoreDNS on port 53 and to the namespace's own pods.

#### Scenario: A test reads the Gitea perimeter
- **WHEN** a test reads `k8s/gitea/networkpolicy.yaml`
- **THEN** its ingress and egress peers and ports are those above, and ports 22 and 2222 are admitted from nowhere

### Requirement: The Gitea admin Secret comes from the keyring
The values SHALL read the admin from the existing Secret `gitea-admin` with `passwordMode: keepUpdated`. The push table SHALL hold `gitea/gitea-admin` in stack `gitea`: key `username` from the literal `gitea_admin`, and key `password` from the keyring key `gitea_admin_password`, required and never generated, which backs the managed secret option `gitea.admin_password` with the environment variable `DEVOPS_CLI_GITEA_ADMIN_PASSWORD`. A change SHALL restart `deployment/gitea`.

#### Scenario: A test reads the push table and the option tables
- **WHEN** a test reads the push table, the option tables and the secret registry
- **THEN** the row, its sources, its restart and the option's keyring key and environment variable are those above

#### Scenario: A dry run of the gitea stack's push
- **WHEN** `devops k8s push-secrets --stack gitea --dry-run` runs
- **THEN** it lists the reads of namespace `gitea`, Secret `gitea-admin` and keyring key `gitea_admin_password`, the apply with placeholders, and the restart of `deployment/gitea`, in order, makes no request and shows no value
