# Release Notes — devops-cli v0.1.7

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.7

### 🐍 Native DevContainer Lifecycle Engine
- **`devops devcontainer run-lifecycle`**: Implemented type-safe, cross-platform Python lifecycle hooks (`--post-create`, `--post-start`, `--all`) replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Complete Environment Bootstrap**: Automated persistent shell history (`~/.bash_history`), completion aliases, SSH key permission hardening (`chmod 0600`), Git SSH commit signing setup, and MCP configuration synchronization.

### 🧠 Enhanced AI Reasoning Scratchpad Buffer
- **`ScratchpadBuffer` Reasoning Context**: Preserves intermediate chain-of-thought, persona analysis notes, and verification hypotheses across multi-agent review stages.
- **Context Degradation Prevention**: Maintains high review fidelity across large multi-file diffs and multi-turn pipeline handovers.

### ⚡ Prompt Token & Latency Optimization
- **Compact Serialization**: Enforced compact JSON serialization (`separators=(",", ":")`) across prompt templates and schemas.
- **Context Streamlining**: Reduced token overhead and improved LLM inference responsiveness for local Ollama nodes and remote API providers.

### 🛡️ Exception Resilience & Storage Standardization
- **Worker Error Recovery**: Robust error handling in parallel review worker pipelines, preventing crashes on isolated file parsing anomalies.
- **Top-Level Storage Persistence**: Standardized all analysis and review metadata persistence under `.data/` at the repository root.

---

## 🚀 Highlights of v0.1.6

### 🛡️ Static SecOps & K8s Security Integrations
- **Aqua Trivy Scanning (`devops scan [repo|image|iac]`)**: Comprehensive vulnerability and secret scanning with automated finding injection into `devsecops` persona reviews.
- **Red Hat Kube-linter (`devops k8s lint`)**: Static analysis of Kubernetes manifests and Helm charts against production security best practices.
- **Derailed Popeye (`devops k8s audit`)**: Live Minikube and Kubernetes cluster health sanitizer checking resource limits, pods, and misconfigurations.
- **Fairwinds Pluto (`devops k8s check-deprecated`)**: Deprecated and removed Kubernetes API version detector.

---

## 🚀 Highlights of v0.1.5

### ☸️ Minikube Infrastructure & Target Service Auto-Configuration
- **`devops k8s configure-urls`**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `argocd.url`, `grafana.url`, and `prometheus.url` in `config.yaml`.
- **Automated `deploy-stack` Integration**: `devops k8s deploy-stack` automatically triggers service URL detection upon completing Helm release deployments.

### ⚡ FastMCP Server Tool Alignment
- **Verified 18 FastMCP Tools**: Fixed CLI subcommand mappings in `src/devops_cli/mcp.py` for `repos_status`, `argo_list`, `argo_status`, `docker_stats`, and `workspace_list`.

### 🛡️ 7-Gate CI Quality Gate
- **Expanded Quality Gate**: Added `devops ci coverage` (`pytest-cov`) and `devops ci security` (`bandit`), expanding the automated CI check to 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`, `trivy`, `kube-linter`, `popeye`, `pluto`
