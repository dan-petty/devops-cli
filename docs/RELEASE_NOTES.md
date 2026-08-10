# Release Notes — devops-cli v1.0.0 (Draft)

> **devops-cli v1.0.0** — Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, ArgoCD, Grafana, and multi-persona AI code reviews.

---

## Highlights

### 🤖 Multi-Persona AI Code Reviews & Verification Loop
- **Expert Persona Engine**: Run expert code reviews across 5 specialized roles: `devsecops`, `architect`, `pm`, `auditor`, and `qa`.
- **Fast Deterministic Segment Metadata**: Step 1/4 metadata generation uses instant static analysis (`SegmentMeta` / `ReviewMeta`) for 100% consistency and sub-millisecond execution time.
- **Finding Verification & Analytics**: Inspect findings (`devops review findings`), validate/invalidate entries (`devops review verify`), and generate accuracy metrics (`devops review stats`).
- **Privacy & SSRF Defenses**: Outbound LLM API requests enforce SSRF validation against loopback/link-local/private-network IP addresses unless explicitly permitted via `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`.

### 🛡️ DevSecOps Security Hardening & Workspace Boundary Guards
- **Python 2 Exception Syntax Remediation**: Replaced legacy comma exception handling (`except Err1, Err2:`) with proper tuple syntax across all subpackages.
- **Path Traversal & Boundary Protection**: Enforced strict `_is_safe_workspace_path` boundary checks in `read_file`, `list_files`, `devops review path`, and `devops workspace add`.
- **Subprocess Safety**: Added explicit timeout guards to all subprocess calls (`kubectl`, `argo`, `gh`, `git config`) and capped `--tail` input bounds.
- **Secret & Network Protection**: Removed unencrypted `PlaintextKeyring` fallbacks when OS keyring fails; protected GitHub PR diff redirects against token header leakage.

### ⚡ Submodule Architecture & Pydantic Domain Models
- **Clean Subpackage Organization**: Built around modular packages: `devops_cli.config`, `devops_cli.core`, `devops_cli.http`, `devops_cli.models`, `devops_cli.crypto`, `devops_cli.git`, `devops_cli.github`, and `devops_cli.commands`.
- **Pydantic-First Data Contracts**: Domain objects (`SegmentMeta`, `ReviewMeta`, `BranchListing`, `ManagedSSHKey`, `SSHKeyInfo`, `GrafanaDashboard`, `PrometheusQueryResult`, `ArgoCDApp`, `ChatMessage`) replace raw untyped dictionaries across all API interactions.

### ☸️ DevContainer & Minikube Infrastructure Automation
- **Automated Stack Deployment**: Scaffolding for ArgoCD, Prometheus, Grafana, and OpenTelemetry Collector in `k8s/`.
- **Minikube Integration**: Post-start lifecycle scripts automatically start minikube (`--driver=docker`) with metrics-server enabled inside the workstation container environment.
- **Cross-Platform SSH Mounting**: Mounts host SSH keys via `${localEnv:HOME}/.ssh` with 0700/0600 permission hardening.

### 🔐 Zero-Plaintext Secret Storage
- **OS Keyring Integration**: All tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the host/container OS keyring using `keyring`. Credentials are never written to config files or environment variables.

---

## Detailed Command Matrix

| Command Group | Command | Description |
|---|---|---|
| **ai** | `devops ai config` | Configure active AI provider (`ollama`, `claude`, `copilot`, `openai`) |
| | `devops ai test` | Verify LLM connectivity and list available models |
| | `devops ai agents` | (Re)generate canonical `AGENTS.md` and thin pointer files |
| **review** | `devops review branch` | Review git branch diff against base branch |
| | `devops review pr` | Fetch GitHub PR diff and review with optional comment posting |
| | `devops review path` | Review specific file or directory pattern respecting `.gitignore` |
| | `devops review findings` | Inspect findings for a review session by verification status |
| | `devops review verify` | Validate or invalidate individual review findings with feedback |
| | `devops review stats` | Compute accuracy metrics and false-positive rates |
| **repos** | `devops repos clone-org` | Batch clone organisation repositories into `repos/<org>/` |
| | `devops repos clone` | Clone standalone repository into `repos/_standalone/` |
| | `devops repos list` | List all local workspace repositories and active branches |
| | `devops repos sync` | Fetch and pull tracking branches across all workspace repos |
| **ssh** | `devops ssh generate` | Generate Ed25519 SSH keypair with 90-day rotation tracking |
| | `devops ssh status` | Check age and status of managed SSH keys |
| | `devops ssh register` | Register SSH key and signing key with GitHub account |
| | `devops ssh rotate` | Rotate SSH keys older than threshold |
| **k8s** | `devops k8s deploy-stack` | Deploy ArgoCD, Prometheus, Grafana, and OTEL to minikube |
| | `devops k8s status` | Show pod status across infrastructure namespaces |
| **argo** | `devops argo list` | List ArgoCD applications |
| | `devops argo workflows list` | List Argo Workflows |
| | `devops argo rollouts list` | List Argo Rollouts |
| **grafana** | `devops grafana dashboards` | Search and list Grafana dashboards |
| | `devops grafana alerts` | List configured Grafana alert rules |
| **prometheus** | `devops prometheus query` | Execute PromQL instant query |
| | `devops prometheus targets` | List Prometheus scrape targets |
| **workspace** | `devops workspace generate` | Regenerate multi-root VS Code `.code-workspace` file |
| | `devops workspace open` | Launch workspace file in VS Code |
| **ci** | `devops ci` | Run full quality gate (pytest, ruff check, ruff format, mypy) |

---

## Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation container environment
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
