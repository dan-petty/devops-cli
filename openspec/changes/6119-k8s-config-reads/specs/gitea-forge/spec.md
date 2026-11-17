## MODIFIED Requirements

### Requirement: Namespace gitea enforces restricted Pod Security and keeps its data
The root kustomization's `k8s/namespaces.yaml` SHALL declare namespace `gitea` with Pod Security `restricted` for enforce, warn and audit, and with `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.

#### Scenario: A test reads the namespaces
- **WHEN** a person runs `uv run devops k8s doctor --stack gitea` on the cluster
- **THEN** the check `pod-security-restricted` passes, and `kubectl get namespace gitea -o yaml` shows the labels and the annotation

### Requirement: Gitea keeps its data on a worker node
Persistence SHALL be on, with claim `gitea-shared-storage` of 10Gi in storage class `local-path`, annotated `helm.sh/resource-policy: keep` and `argocd.argoproj.io/sync-options: Prune=false,Delete=false`. The pod SHALL require a node without the label `node-role.kubernetes.io/control-plane`.

#### Scenario: A test reads the storage values
- **WHEN** a person runs `uv run devops k8s doctor --stack gitea` and `kubectl -n gitea get pods -o wide` on the cluster
- **THEN** the check `volume-retained` passes, and the pod runs on a node without the control-plane label

### Requirement: Gitea is a locked forge with no SSH and no egress need
The values SHALL disable registration, require a sign-in to view, make new repositories private, keep push-to-create off for users and organizations, disable migrations, mirrors and Actions, disable the `update_checker` cron job, set `OFFLINE_MODE`, and turn SSH off (`DISABLE_SSH: true`, `START_SSH_SERVER: false`).

#### Scenario: A test reads the lock-down values
- **WHEN** a person runs `uv run devops k8s doctor --stack gitea` on the cluster
- **THEN** the checks `anonymous-read-refused` and `no-egress` pass, and Service `gitea` exposes no SSH port

### Requirement: Gitea runs rootless and non-root with bounded resources
The values SHALL pin image tag `1.27.3` of the rootless image, run the pod as non-root user and group 1000 with fsGroup 1000 and the `RuntimeDefault` seccomp profile, run each container with no privilege escalation, a read-only root filesystem and all capabilities dropped, request 100m CPU and 256Mi and limit 1 CPU and 1Gi, and render no chart test pod.

#### Scenario: A test reads the image, security and resource values
- **WHEN** `uv run devops k8s lint k8s/gitea` runs kube-linter, and a person runs `kubectl -n gitea get deployment gitea -o yaml` on the cluster
- **THEN** kube-linter reports no finding for the pod, and the image, the security contexts and the resources are those above

### Requirement: The Gitea perimeter admits only Gitea's HTTP port
`k8s/gitea/networkpolicy.yaml` SHALL select every pod in namespace `gitea`, admit TCP 3000 only from Traefik's pods in `kube-system`, the `argocd-repo-server` pods in `argocd` and the namespace's own pods, admit no address range and no SSH port, and allow egress only to CoreDNS on port 53 and to the namespace's own pods.

#### Scenario: A test reads the Gitea perimeter
- **WHEN** a person runs `kubectl -n gitea get networkpolicy -o yaml` on the cluster
- **THEN** its ingress and egress peers and ports are those above, and ports 22 and 2222 are admitted from nowhere
