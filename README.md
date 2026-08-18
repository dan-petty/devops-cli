# devops-cli — Workstation DevOps CLI & Multi-Persona AI Code Reviewer

[![CI Validation](https://github.com/your-org/devops-cli/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Type Checked: Mypy Strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-Enabled-purple.svg)](docs/MCP_TOOLS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DevContainer Native](https://img.shields.io/badge/DevContainer-Native-green.svg)](.devcontainer/devcontainer.json)

`devops-cli` is an enterprise-grade workstation CLI and agentic code analysis platform designed for Site Reliability Engineers and DevOps Practitioners running inside VS Code Dev Containers. It unifies multi-repository infrastructure management (Git, Kubernetes, Kustomize, ArgoCD, Grafana, Prometheus, Docker, SSH) with multi-persona **Agentic LLM code reviews**, OS Keyring secret isolation, active SSRF network guardrails, and automated release orchestration.

---

## 🏛️ SRE Engineering Tenets & Architectural Highlights

- 🔒 **Zero-Plaintext Secret Architecture**: Sensitive tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the OS Keyring via Python `keyring`. Configuration files contain zero plaintext credentials.
- 🛡️ **Active SSRF & Egress Guardrails**: Outbound API requests pass through strict IP validation (`validate_service_url`) blocking private subnets (RFC 1918), loopbacks, and cloud metadata endpoints by default.
- 🤖 **Multi-Persona Agentic Code Review**: Paginated diff analysis across branches and PRs using specialized expert personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) backed by `ScratchpadBuffer` reasoning context and deterministic finding verification.
- ⚙️ **Native DevContainer Lifecycle Engine**: Cross-platform Python lifecycle orchestration (`devops devcontainer run-lifecycle`) replaces legacy shell scripts for post-create and post-start hooks.
- 🚀 **End-to-End Release Cycle Automation**: Native `devops release` subcommands suite (`status`, `prepare`, `check`, `notes`, `tag`) automating version bumping, changelogs, docs sync, and CI validation.
- 🔌 **FastMCP Server & Native Tool Bridge**: Over 25+ infrastructure and analysis tools exposed over Model Context Protocol for seamless integration into AI IDEs and autonomous subagents.

---

## 📚 Architectural & Governance Documentation

- 📐 [**System Architecture & Technical Design (`ARCHITECTURE.md`)**](ARCHITECTURE.md) — Subsystem topologies, multi-agent sequence diagrams, and lifecycle hooks.
- 🔄 [**Release Cycle & Versioning Guide (`RELEASE_CYCLE.md`)**](RELEASE_CYCLE.md) — Semantic versioning, validation checks, and release procedures.
- 🛡️ [**Security Policy & Threat Model (`SECURITY.md`)**](SECURITY.md) — Vulnerability disclosure, SSRF protections, and OS Keyring encryption.
- 🤝 [**Contributor Guidelines (`CONTRIBUTING.md`)**](CONTRIBUTING.md) — Standards, local development with `uv`, and PR workflows.
- 📋 [**Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**](docs/ROUTINE_TASKS.md) — Operational task matrix, cadences, execution order, and troubleshooting protocols.
- 📖 [**Consolidated CLI Reference (`docs/CLI_REFERENCE.md`)**](docs/CLI_REFERENCE.md) — Full subcommand reference.
- 🌐 [**Environment Variables Guide (`docs/ENV_VARS.md`)**](docs/ENV_VARS.md) — System and environment settings.
- ⚡ [**FastMCP Tools Specification (`docs/MCP_TOOLS.md`)**](docs/MCP_TOOLS.md) — Registered MCP tools.

---

## 🚀 Quick Start & Dev Container Setup

```bash
# 1. Clone repository and open inside Dev Container
git clone https://github.com/your-org/devops-cli.git
cd devops-cli

# 2. Inside the Dev Container, sync Python 3.14 dependencies:
uv sync

# 3. Store credentials securely in the OS Keyring
devops config set github.token "ghp_your_personal_access_token"
devops ai config --provider claude
devops config set ai.api_key "sk-ant-..."

# 4. Verify LLM connectivity and run CI validation
devops ai test
devops ci run
```

### 📦 Reusable Dev Container Package (GHCR)

Every release automatically builds and publishes a pre-packaged Dev Container image to the GitHub Container Registry (GHCR):

```bash
# Pull the pre-built Dev Container image directly:
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:latest
```

To use this pre-built image in any repository's `.devcontainer/devcontainer.json`:

```json
{
  "name": "devops-workstation",
  "image": "ghcr.io/dan-petty/devops-cli/devcontainer:latest"
}
```

### Programmatic Python Usage Example


```python
from pathlib import Path
from devops_cli.ai.client import LLMClient
from devops_cli.ai.review import ReviewPipelineOrchestrator

# Initialize unified LLM client and orchestrator
client = LLMClient()
orchestrator = ReviewPipelineOrchestrator(session_id="custom-session", llm_client=client)

# Execute 6-stage review pipeline programmatically
metadata = orchestrator.run_pre_analysis_refresh(Path.cwd())
payloads = orchestrator.init_per_file_payloads(["src/file.py"], metadata)
orchestrator.execute_multi_persona_review(payloads, diff_text_by_file={}, personas=["devsecops", "architect"])
orchestrator.execute_finding_verification(payloads)
orchestrator.execute_finding_reranking(payloads)
summary_data, report_md = orchestrator.generate_consolidated_report(payloads)
```

---

## 📋 Complete Command Matrix


<!-- COMMAND_MATRIX_START -->
| Command Group | Subcommand / Usage | Purpose & Features |
|---|---|---|
| **repos** | `devops repos clone-org [OPTIONS] <org>` | Clone all repos from a GitHub org into repos/<org>/. |
|  | `devops repos clone [OPTIONS] <url>` | Clone an individual repository into repos/_standalone/<name>/. |
|  | `devops repos list [OPTIONS]` | List all cloned repositories. |
|  | `devops repos update [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
|  | `devops repos sync [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
| **ssh** | `devops ssh generate [OPTIONS]` | Generate a new Ed25519 SSH key with today's date suffix. |
|  | `devops ssh register [OPTIONS]` | SSH key generation, rotation, and GitHub registration. |
|  | `devops ssh rotate [OPTIONS]` | Rotate keys older than rotation_days (default 90). |
|  | `devops ssh list [OPTIONS]` | List all managed SSH keys with their age and rotation status. |
|  | `devops ssh audit [OPTIONS]` | List all managed SSH keys with their age and rotation status. |
|  | `devops ssh status [OPTIONS]` | Show the active SSH key and days until rotation. |
| **branches** | `devops branches update [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches sync [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches jira [OPTIONS] <ticket_id>` | Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]. |
|  | `devops branches list [OPTIONS]` | List branches across all repos. |
|  | `devops branches clean [OPTIONS]` | Delete local branches merged into main/master. |
| **devcontainer** | `devops devcontainer init [OPTIONS] <repo_path>` | Scaffold .devcontainer/ in a repository using the standard template. |
|  | `devops devcontainer update [OPTIONS] <repo_path>` | Update the Python image version in an existing devcontainer.json. |
|  | `devops devcontainer validate [OPTIONS]` | Validate .devcontainer/devcontainer.json manifest syntax and configuration schema. |
|  | `devops devcontainer list [OPTIONS]` | List repos with their devcontainer status. |
|  | `devops devcontainer post-create [OPTIONS]` | Execute DevContainer post-create setup tasks (history, shell completions, config prep). |
|  | `devops devcontainer post-start [OPTIONS]` | Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync). |
|  | `devops devcontainer run-lifecycle [OPTIONS]` | Run specified DevContainer lifecycle hook tasks natively in Python. |
| **workspace** | `devops workspace add [OPTIONS] <repo_path>` | Add a folder to the VS Code workspace file. |
|  | `devops workspace remove [OPTIONS] <repo_path>` | Remove a folder from the VS Code workspace file. |
|  | `devops workspace generate [OPTIONS]` | Regenerate the workspace file from all repos in the repos directory. |
|  | `devops workspace open [OPTIONS]` | Open the workspace in VS Code. |
| **install-tools** | `devops install-tools status [OPTIONS]` | Show installation status and versions for all managed tools. |
| **k8s** | `devops k8s contexts` | List kubeconfig contexts and mark the active one. |
|  | `devops k8s switch-context <name>` | Switch active kubeconfig context. |
|  | `devops k8s status` | Show node and pod summary for the current context. |
|  | `devops k8s apply [OPTIONS] <path>` | Apply a Kubernetes manifest (delegates to kubectl). |
|  | `devops k8s logs [OPTIONS] <pod>` | Stream pod logs (delegates to kubectl). |
|  | `devops k8s bootstrap [OPTIONS]` | Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack. |
|  | `devops k8s deploy-stack [OPTIONS]` | Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to minikube. |
|  | `devops k8s configure-urls [OPTIONS]` | Auto-detect Minikube stack URLs and update CLI config. |
|  | `devops k8s port-forward [OPTIONS]` | Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config. |
|  | `devops k8s teardown-stack [OPTIONS]` | Uninstall the k8s infrastructure / LLM stack and delete namespaces. |
|  | `devops k8s rbac-audit [OPTIONS]` | Audit RBAC RoleBindings and ServiceAccounts for overprivileged access. |
|  | `devops k8s lint [OPTIONS] <target>` | Validate K8s manifests and Helm charts using Red Hat Kube-linter. |
|  | `devops k8s audit [OPTIONS]` | Sanitize active K8s/Minikube cluster resource health using Derailed Popeye. |
|  | `devops k8s check-deprecated [OPTIONS] <target>` | Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto. |
| **kustomize** | `devops kustomize build [OPTIONS] <path>` | Build kustomize overlays (delegates to kustomize build). |
|  | `devops kustomize diff <path>` | Show a diff of pending changes (delegates to kubectl diff -k). |
|  | `devops kustomize apply [OPTIONS] <path>` | Apply a kustomization (delegates to kubectl apply -k). |
| **docker** | `devops docker images [OPTIONS]` | List local Docker images. |
|  | `devops docker build [OPTIONS] <context>` | Build a Docker image. |
|  | `devops docker push <image>` | Push a Docker image to a registry. |
|  | `devops docker prune [OPTIONS]` | Remove unused containers, images, and networks. |
| **grafana** | `devops grafana search [OPTIONS]` | Search Grafana dashboards and folders by query string. |
|  | `devops grafana datasources` | List configured datasources. |
|  | `devops grafana alerts` | List alert rules (Grafana 9+ unified alerting). |
|  | `devops grafana dashboards COMMAND [ARGS]...` | Manage Grafana dashboards. |
| **prometheus** | `devops prometheus query [OPTIONS] <expr>` | Execute an instant PromQL query. |
|  | `devops prometheus query-range [OPTIONS] <expr>` | Execute a range PromQL query and summarise the result. |
|  | `devops prometheus rules` | List Prometheus recording and alerting rules. |
|  | `devops prometheus targets` | List active Prometheus scrape targets. |
| **argo** | `devops argo cd COMMAND [ARGS]...` | ArgoCD application management. |
|  | `devops argo workflows COMMAND [ARGS]...` | Argo Workflows management. |
|  | `devops argo rollouts COMMAND [ARGS]...` | Argo Rollouts management. |
| **config** | `devops config show` | Print all configuration values, masking secrets. |
|  | `devops config get <key>` | Print a single configuration value. |
|  | `devops config set <key> <value>` | Set a configuration value. Tokens are stored in the OS keyring. |
|  | `devops config init` | Interactive first-time setup wizard. |
|  | `devops config env-vars [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config env [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config output [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config auth-headless <key> <token>` | Load secret tokens into ephemeral memory for headless CI environments lacking DBus. |
|  | `devops config audit-stream <destination>` | Stream stored audit records to SIEM destination URL. |
| **ci** | `devops ci test [OPTIONS]` | Run the pytest test suite in parallel leveraging all CPU cores. |
|  | `devops ci coverage [OPTIONS]` | Run pytest with parallel code coverage analysis over src/. |
|  | `devops ci lint [OPTIONS]` | Run ruff linter across the project. |
|  | `devops ci format [OPTIONS]` | Check (or apply) code formatting with ruff format. |
|  | `devops ci typecheck` | Run mypy static type-checker strictly targeting Python 3.14 over src/. |
|  | `devops ci audit` | Run uv audit to check for known package vulnerabilities. |
|  | `devops ci security [OPTIONS]` | Run bandit static security vulnerability analysis over src/. |
|  | `devops ci actionlint` | Run actionlint to validate GitHub Actions workflows for syntax and schema errors. |
|  | `devops ci docs` | Verify that documentation is up to date with CLI commands and configuration. |
|  | `devops ci run [OPTIONS]` | Run full CI and return a single pass/fail status. |
| **uv** | `devops uv sync [OPTIONS]` | Sync project dependencies into the virtual environment. |
|  | `devops uv lock [OPTIONS]` | Regenerate the uv lockfile. |
|  | `devops uv python-install [OPTIONS]` | Install project Python version with uv. |
|  | `devops uv run` | Run an arbitrary command using `uv run`. |
| **scan** | `devops scan [OPTIONS] <target>` | Security, vulnerability, secret, and IaC scanner via Aqua Trivy. |
| **ai** | `devops ai config [OPTIONS]` | Show or update AI provider configuration. |
|  | `devops ai models` | List available models for the configured provider. |
|  | `devops ai preload` | Preload configured model into VRAM across all configured Ollama servers. |
|  | `devops ai test [OPTIONS]` | Send a test prompt to verify AI provider connectivity. |
|  | `devops ai agents [OPTIONS]` | Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md). |
|  | `devops ai chat [OPTIONS]` | Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming). |
|  | `devops ai bundle-models [OPTIONS]` | Bundle Ollama model metadata into tarball for air-gapped DevContainers. |
|  | `devops ai pipeline [OPTIONS] <prompt>` | Run a multi-agent Pydantic pipeline with shared DevOps tools. |
|  | `devops ai review COMMAND [ARGS]...` | AI-powered code reviews using expert personas (devsecops, architect, pm, auditor, qa). |
|  | `devops ai analyze COMMAND [ARGS]...` | Analyze codebase metadata and create/update .data/analysis/*-metadata.json files. |
| **review** | `devops review path [OPTIONS] <target>` | Review source files directly (no git required). |
|  | `devops review branch [OPTIONS] <branch_name>` | Review a git branch diff with one or all AI personas. |
|  | `devops review pr [OPTIONS] <number>` | Review a GitHub pull request with one or all AI personas. |
|  | `devops review findings [OPTIONS]` | Inspect structured findings for a review session. |
|  | `devops review verify [OPTIONS] <session>` | Validate or invalidate a review finding, persisting feedback reasons. |
|  | `devops review stats [OPTIONS]` | Compute and display review accuracy statistics across saved sessions. |
|  | `devops review export-feedback [OPTIONS]` | Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning. |
|  | `devops review apply-patch [OPTIONS] <session>` | Apply suggested LLM code fix for a verified finding (v0.1.3). |
| **mcp** | `devops mcp serve [OPTIONS]` | Launch FastMCP server to expose devops-cli tools to MCP clients. |
|  | `devops mcp tools` | List all registered FastMCP tools and descriptions. |
| **docs** | `devops docs generate [OPTIONS]` | Generate comprehensive Markdown or JSON documentation for all CLI commands and tools. |
|  | `devops docs check [OPTIONS]` | Check that generated documentation and README.md are up to date with codebase. |
|  | `devops docs sync-readme [OPTIONS]` | Synchronize the Complete Command Matrix table in README.md with live CLI commands. |
| **release** | `devops release status [OPTIONS]` | Display current release status, versions, tags, changelog, and docs state. |
|  | `devops release prepare [OPTIONS] <version>` | Bump version across pyproject.toml and source, update changelog, and sync docs. |
|  | `devops release pr [OPTIONS]` | Create release branch, commit version bumps, and open a GitHub Release Pull Request. |
|  | `devops release check [OPTIONS]` | Verify release readiness (version consistency, docs freshness, and CI quality gates). |
|  | `devops release notes [OPTIONS]` | Print markdown release notes for a specified or current release version. |
|  | `devops release tag [OPTIONS]` | Create release commit and annotated git tag. |
| **tf** | `devops tf init [OPTIONS] <directory>` | Initialize an OpenTofu working directory. |
|  | `devops tf plan [OPTIONS] <directory>` | Generate and show an OpenTofu execution plan. |
|  | `devops tf apply [OPTIONS] <directory>` | Create or update OpenTofu infrastructure. |
|  | `devops tf destroy [OPTIONS] <directory>` | Destroy OpenTofu-managed infrastructure. |
|  | `devops tf output [OPTIONS] <directory>` | Read an output variable from the OpenTofu state. |
|  | `devops tf validate [OPTIONS] <directory>` | Validate the OpenTofu configuration files in a directory. |
|  | `devops tf fmt [OPTIONS] <directory>` | Rewrites OpenTofu configuration files to canonical format. |
|  | `devops tf status <directory>` | Show OpenTofu directory state, initialization status, and provider plugins. |
|  | `devops tf deploy-cloud [OPTIONS]` | Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP. |
| **tofu** | `devops tofu init [OPTIONS] <directory>` | Initialize an OpenTofu working directory. |
|  | `devops tofu plan [OPTIONS] <directory>` | Generate and show an OpenTofu execution plan. |
|  | `devops tofu apply [OPTIONS] <directory>` | Create or update OpenTofu infrastructure. |
|  | `devops tofu destroy [OPTIONS] <directory>` | Destroy OpenTofu-managed infrastructure. |
|  | `devops tofu output [OPTIONS] <directory>` | Read an output variable from the OpenTofu state. |
|  | `devops tofu validate [OPTIONS] <directory>` | Validate the OpenTofu configuration files in a directory. |
|  | `devops tofu fmt [OPTIONS] <directory>` | Rewrites OpenTofu configuration files to canonical format. |
|  | `devops tofu status <directory>` | Show OpenTofu directory state, initialization status, and provider plugins. |
|  | `devops tofu deploy-cloud [OPTIONS]` | Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP. |
<!-- COMMAND_MATRIX_END -->

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
| | Trivy Vulnerability & Misconfig Engine (`devops scan`) | High | Low | ✅ Completed (v0.1.6) |
| | Kube-linter Manifest Auditor (`devops k8s lint`) | High | Low | ✅ Completed (v0.1.6) |
| | Popeye K8s Cluster Sanitizer (`devops k8s audit`) | High | Low | ✅ Completed (v0.1.6) |
| | Pluto K8s Deprecated API Scanner (`devops k8s check-deprecated`) | High | Low | ✅ Completed (v0.1.6) |
| **Strategic Investments** | Minikube Service Auto-Config & 7-Gate CI | High | High | ✅ Completed (v0.1.5) |
| | DevContainer Shell Script Replacement Engine | High | Medium | ✅ Completed (v0.1.7) |
| | Enhanced AI/LLM Scratchpad Reasoning Buffer | High | Medium | ✅ Completed (v0.1.7) |
| | AI/LLM Prompt Token & Latency Optimization | High | Medium | ✅ Completed (v0.1.7) |
| | AI Agent Pipeline Framework Evaluation & Benchmark | High | Medium | 🔄 Scheduled (v0.1.7) |
| | OpenTelemetry, Prometheus, Grafana & Jaeger via Minikube | High | High | 🔄 Scheduled (v0.1.7) |
| | Line-Level GitHub PR Inline Comments | High | High | ✅ Completed (v0.1.1) |
| | Human Invalidation Feedback Dataset Exporter | High | Medium | ✅ Completed (v0.1.1) |
| | Custom Team Persona Prompt Overrides (`.devops/personas/`) | High | Medium | ✅ Completed (v0.1.1) |
| **Fill-ins** | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Fallback Auth | Medium | Medium | ✅ Completed (v0.1.1) |
| **De-prioritized** | Bare-Metal OS Installers | Low | High | ❌ Rejected (Devcontainer native) |

---

## Working Documentation

- [AGENTS.md](AGENTS.md) — Single source of truth for AI agents.
- [RELEASE_NOTES.md](docs/RELEASE_NOTES.md) — Version release notes and highlights.
- [CHANGELOG.md](CHANGELOG.md) — Historical release and version changes.
- [ROADMAP.md](docs/ROADMAP.md) — Vision, principles, and phased deliverables.
- [PENDING_FEATURES.md](docs/PENDING_FEATURES.md) — Active proposals and feature specifications.
- [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — Operational edge cases and intentional design trade-offs.
- [LOG.md](docs/LOG.md) — Active chronological development and refactoring log.

---

## License

Distributed under the MIT License. See `LICENSE` for details.
