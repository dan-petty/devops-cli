# Release Notes — devops-cli v0.1.5

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.5

### ☸️ Minikube Infrastructure & Target Service Auto-Configuration
- **`devops k8s configure-urls`**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `argocd.url`, `grafana.url`, and `prometheus.url` in `config.yaml`.
- **Automated `deploy-stack` Integration**: `devops k8s deploy-stack` automatically triggers service URL detection upon completing Helm release deployments.

### ⚡ FastMCP Server Tool Alignment
- **Verified 18 FastMCP Tools**: Fixed CLI subcommand mappings in `src/devops_cli/mcp.py` for `repos_status`, `argo_list`, `argo_status`, `docker_stats`, and `workspace_list`. Verified end-to-end tool calls against live cluster endpoints.

### 🛡️ 7-Gate CI Quality Gate
- **Expanded Quality Gate**: Added `devops ci coverage` (`pytest-cov`) and `devops ci security` (`bandit`), expanding the automated CI check to 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).

### 🔒 Security Hardening & Python 3.14 Compatibility
- **Python 3.14 Exception Syntax**: Refactored 19 occurrences of legacy `except Exception, Type:` syntax across 12 modules into standard parenthesized tuples `except (Exception, Type):`.
- **Pydantic Model Overwrite Prevention**: Enhanced `dotted_set()` in `src/devops_cli/config/settings.py` to prevent primitive strings from overwriting top-level `BaseModel` section objects.
- **OWASP LLM01 Prompt Injection Protection**: Documented XML boundary tag sanitization rationale (`&lt;/tag&gt;`) inside untrusted user code diffs.
- **Review Finding Verification Pipeline**: Updated findings status (`VERIFIED`, `MITIGATED`) for automated review sessions and enabled JSONL dataset export via `devops ai review export-feedback`.

### 🤖 AI Backend Model Visibility
- **Active Model Display**: Every AI code review file request now explicitly displays the target LLM model backend and provider handling the prompt.

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
