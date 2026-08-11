# Release Notes — devops-cli v0.1.3

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.3

### 🛠️ Interactive Code Patch Application
- **`devops ai review apply-patch --interactive`**: Render colored git diff previews using Rich console before staging LLM code fixes (`finding.fix`).

### 📦 Air-Gapped Local Model Bundling
- **`devops ai bundle-models`**: Export and package local Ollama model weight manifests for air-gapped DevContainer deployment.

### 🛡️ Kubernetes RBAC Audit Policy Scanner
- **`devops k8s rbac-audit`**: Audit RoleBindings and ServiceAccounts for overprivileged permissions (`*` verbs, cluster-admin bindings).

### 📡 SIEM Live Audit Streamer
- **`devops config audit-stream <dest>`**: Stream structured JSON audit records to Syslog or HTTP log collectors.

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
