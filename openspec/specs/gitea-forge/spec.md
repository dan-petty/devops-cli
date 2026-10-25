# gitea-forge Specification

## Purpose
How the homelab runs Gitea, its internal forge and container registry: the Argo CD Applications and the deploy-stack stack that install it, its chart values, its perimeter, its git host and its admin Secret.

## Requirements

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

### Requirement: The doctor reports each check of the Gitea stack
`devops k8s doctor --stack gitea` SHALL run the checks of the live Gitea stack in place of the cluster rules, and SHALL report the name, the resource, the result and the reason of each check, in order. A failed check SHALL NOT stop the next one. The command SHALL exit 2 when a check fails and 0 when every check passes.

#### Scenario: A healthy Gitea stack
- **WHEN** the process fake and the HTTP fake answer as a healthy Gitea stack
- **THEN** every check passes with its reason, and the command exits 0 with each check in its JSON output

#### Scenario: A failed check
- **WHEN** namespace `gitea` has the enforce level `baseline`
- **THEN** the table marks `pod-security-restricted` FAIL with the reason, and the command exits 2

### Requirement: The doctor checks the Gitea objects in the cluster
The checks SHALL read the cluster with kubectl, each object once, and SHALL pass when Applications `gitea` and `gitea-manifests` are `Synced` and `Healthy`, the volume of claim `gitea-shared-storage` has the reclaim policy `Retain`, namespace `gitea` has the Pod Security enforce level `restricted`, Ingress `gitea/gitea-ingress` has a host that is not `git.example.com`, and `curl https://github.com` in the Gitea container exits 7 or 28.

#### Scenario: One broken object
- **WHEN** one Application, the claim, the volume, the namespace, the Ingress or the egress probe is wrong, or kubectl cannot read an object
- **THEN** only its own check fails, with the reason or kubectl's error

### Requirement: The doctor checks Gitea through the host of the live Ingress
The checks through the host SHALL send each request through the egress-checked client to the host of the live Ingress only, and SHALL pass when `GET /user/login` answers 200, `GET /api/v1/repos/search` with no sign-in answers 401 or 403, and `GET /v2/` answers 401 with a Bearer challenge whose realm is an HTTPS URL on the host. When the Ingress gives no host, these checks and the clone-URL check SHALL fail with `not run` and SHALL send no request.

#### Scenario: One wrong answer
- **WHEN** the sign-in page redirects, the anonymous read answers 200, or the registry gives no Bearer challenge or a realm under another host
- **THEN** only its own check fails, with the reason

#### Scenario: The Ingress gives no host
- **WHEN** the Ingress has no host, or has `git.example.com`
- **THEN** `ingress-host` and the four checks through the host fail, and no HTTP request is sent

### Requirement: The clone-URL check uses a temporary private repository
The check SHALL read the password of `gitea_admin` at run time through the settings layer (`gitea.admin_password`, keyring key `gitea_admin_password`), SHALL make the private repository `devops-doctor-<random>` with `POST /api/v1/user/repos`, and SHALL pass when its `clone_url` is an HTTPS URL on the host and its `ssh_url` does not name the host. Without a password, or when the configuration does not load, it SHALL fail with the reason and send no create.

#### Scenario: The clone URL is wrong
- **WHEN** `clone_url` is under another host, or `ssh_url` names the host
- **THEN** `clone-url` fails with the URL

#### Scenario: The keyring holds no password
- **WHEN** the keyring holds no `gitea_admin_password`
- **THEN** `clone-url` fails and names `devops config set gitea.admin_password`, and no create is sent

#### Scenario: The configuration does not load
- **WHEN** the configuration holds a key that the settings refuse
- **THEN** `clone-url` fails and names the key, no create is sent, and the other checks report

### Requirement: The doctor deletes the temporary repository
The doctor SHALL send `DELETE /api/v1/repos/gitea_admin/<name>` whenever Gitea can hold the repository: after a 201, also when the clone-URL check fails after it, and when the create gets no answer. It SHALL send no delete when Gitea refuses the create. A delete that does not answer 204 or 404 SHALL fail `temporary-repository-deleted` and name the repository.

#### Scenario: The clone-URL check fails
- **WHEN** the clone-URL check fails after a 201
- **THEN** the delete is sent, `temporary-repository-deleted` passes, and Gitea holds no repository

#### Scenario: The create gets no answer
- **WHEN** the create times out
- **THEN** `clone-url` fails with the error, and the delete is sent

#### Scenario: Gitea refuses the create
- **WHEN** the create answers 422
- **THEN** `clone-url` fails with Gitea's message, and no delete is sent

#### Scenario: The delete fails
- **WHEN** the delete answers 500
- **THEN** `temporary-repository-deleted` fails and names the repository to delete by hand

### Requirement: The admin password stays in the Authorization header
The password SHALL go only into the Authorization header of the create and the delete, and into no argument list, log record, output or reason.

#### Scenario: A run with JSON output
- **WHEN** the command runs with JSON output
- **THEN** no output, log record, kubectl argument list or printed request holds the password or its Basic token, and only the create and the delete carry the Authorization header

### Requirement: The dry run of the Gitea checks makes no request
`devops k8s doctor --stack gitea --dry-run` SHALL list each kubectl command and each HTTP request in order, with placeholders for the host, the volume, the password and the repository name, and SHALL start no program, send no request and read no keyring entry. `--stack` SHALL accept only `gitea`.

#### Scenario: A dry run
- **WHEN** `devops k8s doctor --stack gitea --dry-run --context lab` runs
- **THEN** it prints the twelve requests, the body of the create among them, and the process fake, the HTTP fake and the keyring record nothing

#### Scenario: Another stack
- **WHEN** `devops k8s doctor --stack llm` runs
- **THEN** it exits 2 with a usage error, and starts no program
