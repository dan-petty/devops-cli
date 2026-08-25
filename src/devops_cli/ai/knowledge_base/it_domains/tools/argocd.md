# Knowledge Base: ArgoCD (Declarative GitOps Delivery Engine)

## 1. Overview & Purpose

ArgoCD is a declarative, GitOps continuous delivery tool for Kubernetes. It follows the GitOps pattern of using Git repositories as the single source of truth for defining desired application states. In the `devops-cli` ecosystem, ArgoCD automates deployment reconciliation, synchronizes Kubernetes manifests, detects out-of-sync drift, and provides visual auditability.

---

## 2. Usage Information & Architecture

- **GitOps Reconciliation Loop**: Continuously compares live cluster state against the desired state defined in Git and applies automatic or manual sync policies.
- **Multi-Source Support**: Natively renders plain Kubernetes YAML manifests, Kustomize overlays, and Helm charts.
- **CLI Subcommand**: `devops argo` provides status inspection, application listing, sync triggering, and rollback management.

---

## 3. Common & Advanced Commands

### DevOps CLI ArgoCD Commands
```bash
# List all registered ArgoCD applications with sync and health status
devops argo list

# Check detailed status of a specific application
devops argo status --app-name devops-monitoring

# Trigger synchronization of an application
devops argo sync --app-name devops-monitoring

# Rollback an application to a previous revision
devops argo rollback --app-name devops-monitoring --revision 1
```

### Standard `argocd` CLI Commands
```bash
# Log in to ArgoCD server
argocd login localhost:8080 --username admin --password <password> --insecure

# Create a new GitOps application
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default

# Wait for application to reach Synced and Healthy status
argocd app wait guestbook --health

# Inspect resource diff between Git and live cluster
argocd app diff guestbook

# Enable automated sync with self-healing and pruning
argocd app set guestbook --sync-policy automated --auto-prune --self-heal
```

### Sample `Application` Custom Resource
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: workstation-monitoring
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/dan-petty/devops-cli.git
    targetRevision: HEAD
    path: k8s/overlays/monitoring
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 4. Best Practice Guidance

1. **Enable Automated Pruning**: Enable `--auto-prune` so that resources removed from the Git repository are cleanly deleted from the cluster.
2. **Self-Healing**: Configure `--self-heal` to automatically revert manual cluster edits (`kubectl edit`) and maintain Git as the single source of truth.
3. **App of Apps Pattern**: Use an "App of Apps" root application to manage multiple child applications declaratively.
4. **Sync Waves & Hooks**: Use `argocd.argoproj.io/sync-wave` annotations to order resource deployments (e.g. CRDs and namespaces before deployments).

---

## 5. Security Recommendations & Zero-Trust Policies

- **Rotate Initial Admin Password**: Immediately delete or rotate the default `argocd-initial-admin-secret` after cluster bootstrap.
- **SSO & RBAC Integration**: Bind user access through OAuth/OIDC (GitHub, Dex, Okta) with strict read-only and write project permissions.
- **Repository Credentials**: Store private repository SSH deploy keys or GitHub App secrets securely in Kubernetes secrets (`type: git`).

---

## 6. General Standards & Reference Guidelines

- **Namespace**: Standard ArgoCD deployments reside in the `argocd` namespace.
- **Health Checks**: Implement standard Kubernetes readiness and liveness probes so ArgoCD can evaluate application health accurately.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [argo-cd.readthedocs.io](https://argo-cd.readthedocs.io/)
- **Public Git Repository**: [github.com/argoproj/argo-cd](https://github.com/argoproj/argo-cd)
- **Published Container Image**: [quay.io/argoproj/argocd](https://quay.io/repository/argoproj/argocd)
- **DevOps CLI ArgoCD Automation**: [src/devops_cli/commands/argo.py](../../../../commands/argo.py)
