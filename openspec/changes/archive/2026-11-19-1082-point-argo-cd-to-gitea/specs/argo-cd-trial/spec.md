# argo-cd-trial Specification

## Purpose
Deploys transient trial workloads from internal Gitea branches into fenced cluster namespaces using Argo CD.

## ADDED Requirements

### Requirement: AppProject trial definition
`k8s/argocd/apps/projects.yaml` SHALL declare an AppProject named `trial` in namespace `argocd`.
Its `sourceRepos` SHALL contain only `http://gitea-http.gitea.svc.cluster.local:3000/*/*`.
Its `destinations` SHALL permit only `namespace: trial-*` on `https://kubernetes.default.svc`.
Its `clusterResourceWhitelist` SHALL be empty (`[]`).

#### Scenario: AppProject trial structure
- **WHEN** the projects manifest is loaded
- **THEN** AppProject `trial` restricts sourceRepos to in-cluster Gitea, destinations to `trial-*`, and whitelist to empty

### Requirement: Orphaned resources ignore list
The `homelab` AppProject in `k8s/argocd/apps/projects.yaml` SHALL ignore orphaned Applications matching `trial-*`.

#### Scenario: Trial applications ignored as orphans
- **WHEN** an Application named `trial-feature-x` exists in namespace `argocd`
- **THEN** Argo CD does not report it as an orphaned resource of project `homelab`

### Requirement: Mainline application git safety
Every Git repository source in manifests under `k8s/argocd/` SHALL point to `https://github.com/dan-petty/devops-cli.git`.
No Git repository source in manifests under `k8s/argocd/` SHALL point to Gitea.

#### Scenario: Mainline GitOps safety check
- **WHEN** k8s gate checks inspect all Application manifests under `k8s/argocd/`
- **THEN** all Git sources point to GitHub and no Git source points to Gitea

### Requirement: Argo CD network policy egress to Gitea
`k8s/argocd/networkpolicy.yaml` SHALL permit egress traffic from `argocd` namespace pods to namespace `gitea` on TCP port 3000.

#### Scenario: Argo CD pulls git repositories from Gitea
- **WHEN** `argocd-repo-server` initiates an HTTP request to `gitea-http.gitea.svc.cluster.local:3000`
- **THEN** the network policy egress rules allow TCP traffic on port 3000

### Requirement: Argo CD Gitea repository credential Secret
`CLUSTER_SECRETS` SHALL define `argocd/gitea-repo-creds` under stack `gitea`, gated by namespace `gitea`.
It SHALL set label `argocd.argoproj.io/secret-type: repo-creds`.
It SHALL set literal entries `url: http://gitea-http.gitea.svc.cluster.local:3000/` and `type: git`.
It SHALL read username from `gitea.argocd_username` and password from `gitea.argocd_token`.

#### Scenario: Pushing secrets when Gitea namespace exists
- **WHEN** `devops k8s push-secrets` runs on a cluster with namespace `gitea`
- **THEN** Secret `argocd/gitea-repo-creds` is created with repo-creds label and Gitea URL

#### Scenario: Pushing secrets when Gitea namespace is absent
- **WHEN** `devops k8s push-secrets --stack gitea` runs on a cluster without namespace `gitea`
- **THEN** Secret `argocd/gitea-repo-creds` is skipped and no error is raised

### Requirement: CLI commands for trial lifecycle
The CLI SHALL provide `devops argo cd trial start`, `end`, and `list`.

#### Scenario: Starting a trial application
- **WHEN** `devops argo cd trial start --branch feature --path k8s/monitoring` runs
- **THEN** it validates branch and path on Gitea, creates Namespace `trial-feature`, and applies Application `trial-feature`

#### Scenario: Ending a trial application
- **WHEN** `devops argo cd trial end trial-feature` runs
- **THEN** it deletes Application `trial-feature`, waits for resource removal, and deletes Namespace `trial-feature`

#### Scenario: Listing trial applications
- **WHEN** `devops argo cd trial list` runs
- **THEN** it displays all Applications in project `trial` with branch, path, sync status, health, and age
