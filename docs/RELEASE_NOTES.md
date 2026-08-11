# Release Notes — devops-cli v0.1.2

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.2

### ☸️ Multi-Cluster Kubeconfig Management
- **`devops k8s switch-context <name>`**: Switch active Kubernetes contexts and manage namespace access configuration.

### 📜 SIEM Audit Trail Logger
- **`devops_cli.core.audit`**: Record structured JSON execution event records (`AuditRecord`) to `.data/logs/audit.jsonl` or custom destination via `DEVOPS_CLI_AUDIT_LOG_DEST`.

### 🛠️ Automated Code Patch Application
- **`devops ai review apply-patch <session> --index N`**: Interactively stage suggested LLM code fixes (`finding.fix`) to workspace source files.

### 🧪 Subcommand Dry-Run Pydantic Expansion
- **`CommandDryRunResult`**: Expanded structured JSON dry-run responses across `argo`, `grafana`, `prometheus`, `devcontainer` commands.

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
