# devops-cli — Workstation DevOps CLI & Multi-Persona AI Code Reviewer

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DevContainer Native](https://img.shields.io/badge/DevContainer-Native-green.svg)](.devcontainer/devcontainer.json)

`devops-cli` is a workstation CLI for DevOps Engineers running inside VS Code Dev Containers. It integrates multi-repository infrastructure automation (Git, Kubernetes, Kustomize, ArgoCD, Grafana, Prometheus, Docker, SSH) with multi-persona **Agentic LLM code reviews**, OS keyring secret isolation, SSRF defenses, and human-in-the-loop finding verification.

---

## Key Capabilities

- **Multi-Persona AI Code Reviews (`devops ai review`)**: Paginated reviews across Git branches, GitHub Pull Requests, or local paths with domain-specialized AI personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`).
- **Finding Verification & Analytics**: Inspect findings (`devops ai review findings`), validate/invalidate entries (`devops ai review verify`), and compute persona accuracy metrics (`devops ai review stats`).
- **Zero-Plaintext Secret Storage**: Sensitive tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the OS Keyring via `keyring`.
- **SSRF & Network Egress Safeguards**: Network targets (`validate_service_url`) block non-public IP connections unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is explicitly set.
- **Complete DevOps Automation**: Single entrypoint for managing repositories, SSH key rotation, Kubernetes clusters, ArgoCD applications, Grafana dashboards, Prometheus metrics, Docker resource pruning, workspace files, tool installation, and virtual environments.

---

## Quick Start & Dev Container Setup

```bash
# 1. Clone repository and open inside Dev Container
git clone https://github.com/your-org/devops-cli.git
cd devops-cli

# 2. Inside the Dev Container, sync Python 3.14 dependencies:
uv sync

# 3. Store credentials in the OS Keyring
devops config set github.token "ghp_your_personal_access_token"
devops ai config --provider claude
devops config set ai.api_key "sk-ant-..."

# 4. Verify LLM connectivity and run quality gate
devops ai test
devops ci
```

---

## Complete Command Matrix

| Command Group | Subcommand / Usage | Purpose & Features |
|---|---|---|
| **ai** | `devops ai config --provider <p>` | Set LLM provider (`ollama`, `claude`, `copilot`, `openai`) |
| | `devops ai test` | Verify LLM network connectivity and model list |
| | `devops ai agents` | (Re)generate canonical `AGENTS.md` and pointer files |
| | `devops ai review branch [<branch>]` | Review branch git diff against base using AI personas (alias: `devops review`) |
| | `devops ai review pr <number> [--post]` | Review GitHub PR diff; optionally post summary as PR comment |
| | `devops ai review path [<target>]` | Review local files respecting `.gitignore` exclusions |
| | `devops ai review findings [<session>]` | Inspect structured review findings by verification status |
| | `devops ai review verify <session> --index N` | Validate (`verified`) or invalidate (`invalidated`) finding |
| | `devops ai review export-feedback` | Export invalidated findings into JSONL benchmark dataset for prompt tuning |
| | `devops ai review apply-patch <session>` | Interactively stage suggested LLM code fixes (`finding.fix`) to workspace |
| | `devops ai review stats` | View accuracy metrics and false-positive rates per persona |
| | `devops ai pipeline [<prompt>]` | Run multi-agent Pydantic pipeline with shared DevOps & MCP tools |
| | `devops ai bundle-models` | Package local Ollama model weight manifests for air-gapped DevContainers |
| **config** | `devops config show` | Display current CLI configuration and active env var overrides |
| | `devops config output` | Display specification for all 30 environment variables |
| | `devops config auth-headless` | Load secret tokens into memory for headless DBus-less CI environments |
| | `devops config audit-stream <dest>` | Stream stored JSON audit records to SIEM destination URL |
| **repos** | `devops repos clone-org --org <org>` | Batch clone all repositories in a GitHub organization |
| | `devops repos clone <url>` | Clone standalone repository into workspace |
| | `devops repos list` | List local workspace repositories and active git branches |
| | `devops repos sync [--all]` | Fetch and pull tracking branches across workspace repos |
| | `devops repos status` | Display uncommitted changes and branch drift across workspace |
| **ssh** | `devops ssh generate [--email <e>]` | Generate ED25519 keypair (`~/.ssh/id_ed25519-YYYYMMM[DD]`) |
| | `devops ssh status` | Inspect age and rotation status of managed SSH keys |
| | `devops ssh register` | Register SSH key and signing key with GitHub account |
| | `devops ssh rotate` | Rotate SSH keys older than 90 days and update GitHub |
| | `devops ssh audit` | Audit SSH key expiration dates and key file permissions |
| **k8s** | `devops k8s deploy-stack` | Deploy ArgoCD, Prometheus, Grafana, OTEL to minikube and configure URLs |
| | `devops k8s configure-urls` | Auto-detect Minikube monitoring stack NodePort URLs (ArgoCD, Grafana, Prometheus) |
| | `devops k8s status` | Display pod status across infrastructure namespaces |
| | `devops k8s switch-context <ctx>` | Switch active Kubernetes context and cluster namespace |
| | `devops k8s rbac-audit` | Audit RBAC RoleBindings and ServiceAccounts for overprivileged access |
| | `devops k8s pods [--namespace <ns>]` | List pod status with RFC 1123 label filtering |
| | `devops k8s logs <pod> --container <c>` | Stream container logs safely with bounded `--tail` |
| | `devops k8s apply -f <file>` | Apply Kubernetes manifest via `kubectl` |
| **kustomize** | `devops kustomize build <dir>` | Build and validate Kustomize overlay manifests |
| **argo** | `devops argo list` | List ArgoCD applications |
| | `devops argo status --app <app>` | Check ArgoCD application health and sync status |
| | `devops argo sync --app <app>` | Trigger ArgoCD application sync operation |
| | `devops argo workflows list` | List active and historical Argo Workflows |
| | `devops argo rollouts list` | List Argo Rollouts and deployment strategy status |
| **grafana** | `devops grafana dashboards` | Search and list Grafana dashboards by tag or query |
| | `devops grafana alerts` | List active Grafana alert rules and firing states |
| | `devops grafana search --query <q>` | Search Grafana dashboards by query string |
| **prometheus** | `devops prometheus query "<promql>"` | Execute PromQL instant query against Prometheus |
| | `devops prometheus targets` | List Prometheus active scrape targets and health |
| **docker** | `devops docker prune` | Prune dangling Docker containers, networks, and volumes |
| | `devops docker clean` | Deep clean unused Docker images and build cache |
| | `devops docker stats` | Display resource usage metrics for running containers |
| **workspace** | `devops workspace generate` | Regenerate multi-root VS Code `.code-workspace` file |
| | `devops workspace open` | Open multi-root workspace file in VS Code |
| | `devops workspace add <dir>` | Add directory to workspace file with boundary checks |
| | `devops workspace list` | List configured directories in active workspace file |
| **install-tools**| `devops install-tools [tools...]` | Install verified DevOps binaries with SHA-256 checksums |
| | `devops install-tools check` | Verify presence and versions of required CLI binaries |
| **config** | `devops config show` | Display configuration settings with masked secret tokens |
| | `devops config get <key>` | Get specific configuration value |
| | `devops config set <key> <val>` | Set configuration setting or store secret in OS keyring |
| | `devops config output [--export\|--json]`| Output environment variables available for configuration |
| **ci** | `devops ci` | Run 7-check quality gate (test, coverage, lint, format, typecheck, audit, security) |
| | `devops ci test\|coverage\|lint\|format\|typecheck\|audit\|security` | Execute individual CI quality checks |
| **branches** | `devops branches list` | List local and remote tracking branches across repos |
| | `devops branches prune` | Delete local tracking branches merged into main |
| | `devops branches sync` | Synchronize branch state across workspace repositories |
| **devcontainer**| `devops devcontainer init` | Scaffold `.devcontainer/` setup from Jinja2 templates |
| | `devops devcontainer up` | Launch Dev Container environment via VS Code CLI |
| **uv** | `devops uv sync` | Sync Python 3.14 virtual environment dependencies |
| | `devops uv add <pkg>` | Add dependency to `pyproject.toml` and sync |
| | `devops uv remove <pkg>` | Remove dependency from `pyproject.toml` and sync |
| | `devops uv python-install <ver>` | Install Python runtime version via `uv` |
| **mcp** | `devops mcp serve [--transport stdio\|sse] [--port 8000]` | Launch FastMCP server exposing devops-cli tools to MCP clients |
| | `devops mcp tools` | Print Rich table of all registered FastMCP tools and descriptions |

---

## AI Review Engine & Personas

- **DevSecOps (`--persona devsecops`)**: OWASP Top 10, secret leaks, supply chain vulnerabilities, Docker/IaC security misconfigurations.
- **Architect (`--persona architect`)**: SOLID principles, clean architecture/DDD, microservice coupling, observability, API contract design.
- **Project Manager (`--persona pm`)**: Scope risk, breaking changes, test coverage adequacy, deployment rollback readiness, action items.
- **Auditor (`--persona auditor`)**: Regulatory compliance frameworks (NIST SP 800-53, PCI-DSS v4.0, SOC 2 Type II) with exact control IDs.
- **QA / Test Engineer (`--persona qa`)**: Regression prevention, test coverage gaps, edge cases, pytest code skeletons, validation steps.

---

## Local Workstation Model & Security Architecture

1. **Local Workstation Timeouts**: High timeouts (`DEFAULT_REVIEW_TIMEOUT_SECONDS = 3600.0`, `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) support local LLM inference (CPU/GPU Ollama) and corporate proxies.
2. **Key Material Mounting**: `${localEnv:HOME}/.ssh` is bind-mounted by design into `.devcontainer` for local SSH key generation and 90-day rotation.
3. **SSRF Protections**: `validate_service_url` blocks non-public IPs unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
4. **Workspace Boundary Guards**: Path traversal checks (`_is_safe_workspace_path`) enforce repository boundaries on file commands.
5. **Checksum Verification**: `devops install-tools` validates SHA-256 checksums before writing binaries to disk.
6. **Automated Design Justification & Documentation Maintenance**: Non-instructional, reference-backed inline comments (`# NOTE (Design Justification - <REF>): ...`) automatically document intentional design trade-offs directly above target code constructs, and project documentation (`AGENTS.md`, `README.md`, `CLAUDE.md`, `.github/copilot-instructions.md`) is routinely updated whenever code or prompt conventions evolve.

---

## Strategic Prioritization Matrix (Value vs. Effort)

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | RFC 1123 Input Sanitization & Path Traversal Guards | High | Low | ✅ Completed |
| | Human Finding Verification CLI & Accuracy Stats | High | Low | ✅ Completed |
| | Fast Deterministic Static Segment Metadata (`SegmentMeta`) | High | Low | ✅ Completed |
| | Prompt Isolation Guardrails & Boundary Tag Sanitization | High | Low | ✅ Completed |
| | `devops config output` Env Var Specification Command | High | Low | ✅ Completed |
| **Strategic Investments** | Line-Level GitHub PR Inline Comments | High | High | 🔄 Short-Term (Q3 2026) |
| | Human Invalidation Feedback Dataset Exporter | High | Medium | 🔄 Short-Term (Q3 2026) |
| | Custom Team Persona Prompt Overrides (`.devops/personas/`) | High | Medium | 🔄 Short-Term (Q3 2026) |
| **Fill-ins** | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Fallback Auth | Medium | Medium | 🔄 Mid-Term (Q4 2026) |
| **De-prioritized** | Bare-Metal OS Installers | Low | High | ❌ Rejected (Devcontainer native) |

---

## Working Documentation

- [AGENTS.md](AGENTS.md) — Single source of truth for AI agents.
- [ROADMAP.md](docs/ROADMAP.md) — Vision, principles, and phased deliverables.
- [PENDING_FEATURES.md](docs/PENDING_FEATURES.md) — Active proposals and feature specifications.
- [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — Operational edge cases and intentional design trade-offs.

---

## License

Distributed under the MIT License. See `LICENSE` for details.
