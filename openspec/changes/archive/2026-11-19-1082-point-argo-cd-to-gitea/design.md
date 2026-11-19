# Design

## Decisions

### 1. Dedicated AppProject `trial` with strict namespace and repo boundaries
- `sourceRepos`: exactly `http://gitea-http.gitea.svc.cluster.local:3000/*/*`.
- `destinations`: exactly `namespace: trial-*` on `https://kubernetes.default.svc`.
- `clusterResourceWhitelist`: `[]` (empty list; trial applications cannot create cluster-scoped objects or namespaces).
- Pod Security standard: namespaces carry `restricted` for enforce, warn, and audit.

### 2. Safety Rule: Mainline GitOps stays on GitHub
- All git sources under `k8s/argocd/apps/` continue to point to `https://github.com/dan-petty/devops-cli.git`.
- Gitea is not used for mainline applications in git; a broken Gitea does not stop cluster GitOps.

### 3. In-cluster HTTP for repository credentials
- Argo CD communicates with Gitea using internal cluster DNS: `http://gitea-http.gitea.svc.cluster.local:3000/`.
- Repository credential Secret `argocd/gitea-repo-creds` contains a scoped `read:repository` token (`gitea.argocd_token`).
- `ClusterSecret` row carries `gate_namespace="gitea"` to skip pushing on clusters without Gitea.

### 4. CLI lifecycle commands for trial environments
- `devops argo cd trial start`: verifies branch and path on Gitea, creates Namespace `trial-<name>`, and applies Application `trial-<name>` in project `trial`.
- `devops argo cd trial end`: deletes Application `trial-<name>`, waits for resources-finalizer, and deletes Namespace `trial-<name>`. Fails if name does not match `trial-*`.
- `devops argo cd trial list`: lists Applications in project `trial`.

## Rejected Alternatives

### 1. Pointing mainline Argo CD applications to Gitea
- Rejected: Gitea copy of `main` requires manual synchronization and creates circular dependencies during outages.

### 2. Using public HTTPS via Cloudflare tunnel for in-cluster Argo CD traffic
- Rejected: Public routing exposes internal cluster credentials to Cloudflare tunnel egress unnecessarily.

### 3. Permitting cluster-scoped resources in trial applications
- Rejected: Cluster-scoped resources allow trial manifests to escape isolation or overwrite shared cluster state.
