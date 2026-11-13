# devops-cli — Workstation DevOps CLI & Automated Code Review Platform

[![CI Validation](https://github.com/dan-petty/devops-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/dan-petty/devops-cli/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Type Checked: Mypy Strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-Enabled-purple.svg)](docs/MCP_TOOLS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/dan-petty/devops-cli/blob/main/LICENSE)
[![DevContainer Native](https://img.shields.io/badge/DevContainer-Native-green.svg)](https://github.com/dan-petty/devops-cli/blob/main/.devcontainer/devcontainer.json)

`devops-cli` is an enterprise-grade workstation CLI and agentic code analysis platform designed for Site Reliability Engineers and DevOps Practitioners running inside VS Code Dev Containers. It unifies multi-repository infrastructure management (Git, Kubernetes, Kustomize, ArgoCD, Grafana, Prometheus, Docker, SSH) with tool-anchored **Automated Code Review & Group Analysis**, OS Keyring secret isolation, and active SSRF network guardrails.

---

## SRE Engineering Tenets & Architectural Highlights

- **Zero-Plaintext Secret Architecture**: Sensitive tokens (`grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the OS Keyring via Python `keyring`. GitHub access is gh's own login: each process acts as the one identity `gh auth token` returns. Configuration files contain zero plaintext credentials.
- **Active SSRF & Egress Guardrails**: Every HTTP client is built by `devops_cli.http.entry`, with the egress transport of `devops_cli.http.client`. Each client checks the address it dials, at the connect and on every redirect, against its egress level (public, loopback or private). A rebinding DNS answer cannot slip past a check made earlier. Kept pre-flight checks (Qdrant, kubectl manifest apply, container engine endpoint, config init wizard) call `vet_addresses` at their level. Cloud metadata endpoints are refused at every level.
- **Automated Code Review & Group Analysis**: Tool-anchored defect detection across branches and PRs combining static scanners, vulnerability analysis, and bounded model analysis for admitted finding groups.
- **Native DevContainer Lifecycle Engine**: Cross-platform Python lifecycle commands (`devops devcontainer post-create` / `post-start`, both runnable together via `devops devcontainer run-lifecycle`) implement the post-create and post-start hooks.
- **FastMCP Server & Native Tool Bridge**: Infrastructure and analysis tools exposed over Model Context Protocol for seamless integration into AI IDEs and autonomous subagents.

---

## Software Maturity, Lifecycle & Versioning Policy

> [!IMPORTANT]
> **Pre-1.0 Alpha Software Status**: `devops-cli` is active **alpha software** prior to release `1.0.0`. Until at least release `1.0.0`, there is **no intention of maintaining backwards compatibility**. The codebase is intentionally kept clean of legacy references, obsolete shims, and compatibility remnants at all times so that it can reach architectural maturity at a reasonable rate.
>
> **Post-1.0 Semantic Versioning**: Any version released after `1.0.0` will strictly adhere to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`) and follow enterprise change management best practices, including runtime feature flags, structured multi-release deprecation cycles, and automated migration functionality.

---

## Architectural & Governance Documentation

- [**System Architecture & Technical Design (`ARCHITECTURE.md`)**](ARCHITECTURE.md) — Subsystem topologies, multi-agent sequence diagrams, and lifecycle hooks.
- [**Release Cycle & Versioning Guide (`RELEASE_CYCLE.md`)**](RELEASE_CYCLE.md) — How release-please releases from `main`, and what a person does to release.
- [**Security Policy & Threat Model (`SECURITY.md`)**](SECURITY.md) — Vulnerability disclosure, SSRF protections, and OS Keyring encryption.
- [**Contributor Guidelines (`CONTRIBUTING.md`)**](CONTRIBUTING.md) — Standards, local development with `uv`, and PR workflows.
- [**Documentation Overview (`docs/index.md`)**](docs/index.md) — Overview and table of contents for the documentation site.
- [**Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**](docs/ROUTINE_TASKS.md) — Operational task matrix, cadences, execution order, and troubleshooting protocols.
- [**CLI Reference (`docs/CLI_REFERENCE.md`)**](docs/CLI_REFERENCE.md) — The command groups and the command matrix, with a link to the page of each group.
- [**Environment Variables Guide (`docs/ENV_VARS.md`)**](docs/ENV_VARS.md) — System and environment settings.
- [**FastMCP Tools Specification (`docs/MCP_TOOLS.md`)**](docs/MCP_TOOLS.md) — Registered MCP tools.
- [**Configuration Reference (`docs/CONFIGURATION.md`)**](docs/CONFIGURATION.md) — Every setting, and the order in which sources set it.
- [**Exit Code & Error Catalog (`docs/ERRORS.md`)**](docs/ERRORS.md) — Error codes, exit codes and their categories.
- [**Telemetry & Tracing Reference (`docs/TELEMETRY.md`)**](docs/TELEMETRY.md) — Metrics, spans and the way they reach Prometheus.
- [**AI and RAG Cheatsheet (`docs/cheatsheets/ai_and_rag.md`)**](docs/cheatsheets/ai_and_rag.md) — Managed repository ingestion and semantic search reference.
- [**Knowledge Base Catalog (`docs/KNOWLEDGE_BASE.md`)**](docs/KNOWLEDGE_BASE.md) — The manuals that ground the AI commands.
- [**OpenTofu Modules (`tf/README.md`)**](tf/README.md) — Managed Kubernetes cluster modules.
- [**Agent Records (`docs/agent/README.md`)**](docs/agent/README.md) — Compacted records of the early development phases.
- [**Dashboard Tabs Audit (`docs/DASHBOARD_TABS_AUDIT.md`)**](docs/DASHBOARD_TABS_AUDIT.md) — Audit of five dashboard tabs against open terminal tools.

---

## Quick Start & Dev Container Setup

```bash
# 1. Clone repository and open inside Dev Container
git clone https://github.com/dan-petty/devops-cli.git
cd devops-cli

# 2. Inside the Dev Container, sync Python 3.14 dependencies. The Dev Container puts .venv/bin
#    first on PATH, so `devops` is the editable install of this checkout:
uv sync

# 3. Log in to GitHub with gh, and store other credentials in the OS Keyring
gh auth login
devops ai config --provider claude
devops config set ai.api_key "sk-ant-..."

# 4. Verify LLM connectivity and run CI validation
devops ai test
devops ci run
```

### Reusable Dev Container Package (GHCR)

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

> [!TIP]
> For advanced configuration, Dockerfile extensions, Codespaces setup, and CLI scaffolding, see the [**Complete Dev Container Usage Guide**](docs/DEVCONTAINER_USAGE.md).

### Programmatic Python Usage Example


```python
from pathlib import Path
from devops_cli.ai.client import LLMClient
from devops_cli.ai.review import ReviewPipelineOrchestrator

# Initialize unified LLM client and orchestrator
client = LLMClient()
orchestrator = ReviewPipelineOrchestrator(
    session_id="custom-session", llm_client=client, target_dir=Path.cwd()
)

# Run the review stages programmatically
metadata = orchestrator.run_pre_analysis_refresh(Path.cwd())
payloads = orchestrator.init_per_file_payloads(["src/file.py"], metadata)
summary_data, report_md = orchestrator.generate_consolidated_report(payloads)
```

---

## AI Assistant Personas

Specialized personas available for interactive conversations via `devops ai chat --persona <name>`:

- **DevSecOps (`--persona devsecops`)**: Security threat modeling, OWASP risk identification, secret leaks, supply chain posture.
- **Architect (`--persona architect`)**: SOLID principles, clean architecture/DDD, microservice coupling, observability, API contract design.
- **Project Manager (`--persona pm`)**: Scope risk, delivery milestones, release readiness, dependencies, roadmap alignment.
- **Auditor (`--persona auditor`)**: Regulatory compliance frameworks (NIST SP 800-53, PCI-DSS v4.0, SOC 2 Type II) with exact control IDs.
- **QA / Test Engineer (`--persona qa`)**: Regression prevention, test coverage gaps, edge cases, pytest code skeletons, validation steps.
- **Challenger (`--persona challenger`)**: Argues against a claim, design, or plan put to it in chat and names the evidence that would settle it.

Each persona chats with its role, the chat task and its own prompt (`src/devops_cli/ai/personas/<name>/prompt.md`). Each persona has its own tool set and its own RAG search terms. Challenger only reads and searches: it gets no scanner, cluster or MCP tool.

---

## Local Workstation Model & Security Architecture

1. **Local Workstation Timeouts**: High timeouts (`DEFAULT_HTTP_TIMEOUT_SECONDS = 3600.0` per LLM request, `DEFAULT_REVIEW_TIMEOUT_SECONDS = 1200.0` per review request, unless `ai.timeout` or `ai.tasks.<task>.timeout` sets one; `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) support local LLM inference (CPU/GPU Ollama) and corporate proxies.
2. **Key Material Mounting**: `${localEnv:HOME}/.ssh` is bind-mounted by design into `.devcontainer` for local SSH key generation and 90-day rotation.
3. **SSRF Protections**: Every HTTP client is built by the `devops_cli.http.entry` entry point (tool downloads, the Tavily search call, Vault, the `k8s://` proxy and cluster-service clients, Loki, the Grafana, Prometheus and Argo CD clients and their token calls, the sandbox probe, the sandbox metrics scrape, Tempo, the LLM client base, the LLM gateway probes and model query, the `devops ai gateway load` query, the embeddings engine, the pydantic-ai models, the pricing fetch, the documentation crawler, the OSV, Shodan InternetDB and Cloudflare Radar lookups, and the Cloudflare API client). Each client has an egress level (`devops_cli.http.egress`) and resolves a host once, at the connect, dialling only the addresses its level admits. Kept pre-flight callers that do not dial through an httpx2 client (qdrant-client, `devops k8s apply` with manifest URLs, Docker engine endpoint) or dial nothing (`devops config init` wizard) call `vet_addresses` directly at their level. The in-process `kubernetes` client (urllib3) is not checked at the connect: it is trusted because its address comes from the operator's kubeconfig or the in-cluster environment. Untrusted URLs (tool downloads, the pages of the documentation crawler), the default pricing registry and the fixed public APIs (OSV, Shodan InternetDB, Cloudflare Radar and the Cloudflare API) are public-only whatever the configuration says. A service URL from the user's own configuration (Ollama, Qdrant, the LLM gateway, a provider's `api_base_url`, `grafana.url`, `prometheus.url`, `argocd.url`) may name loopback, and a private address once `ai.allow_private_network` (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`) is set. Internal infrastructure clients (Vault, the `k8s://` proxy, Loki, the `devops ai gateway connect` probe) reach private addresses. Cloud metadata addresses are refused at every level. Clients of the entry point ignore `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY`.
4. **Workspace Boundary Guards**: Path traversal checks (`_is_safe_workspace_path`) enforce repository boundaries on file commands.
5. **Checksum Verification**: `devops install-tools` installs every tool only from `tools.lock` (`src/devops_cli/tools_lock/`), at an exact version. A binary is checked against the lock's SHA-256 for its platform, a Python tool (Semgrep, Bandit, and ansible-core with ansible-runner, which links only `ansible-runner`) installs with `uv pip sync --require-hashes` into a virtual environment of its own, and a Node tool (OpenSpec, Dev Containers CLI) installs with `npm ci --ignore-scripts` from a committed `package-lock.json`, which npm checks against the sha512 of every package (`npm` must already be on PATH); a mismatch is refused and the command exits 1. `devops install-tools --check` lists each tool not linked at its locked version.
6. **Automated Design Justification & Documentation Maintenance**: Non-instructional, reference-backed inline comments (`# NOTE (Design Justification - <REF>): ...`) automatically document intentional design trade-offs directly above target code constructs, and a change updates the document that owns each rule it changes. `AGENTS.md` routes each kind of task to that document.

---

## Strategic Prioritization Matrix & Product Roadmap

The roadmap lives on GitHub: the issues are its items, their labels hold their Status, Priority, Value and Effort (`status/*`, `priority/*`, `value/*`, `effort/*`, [ADR 0016](docs/adr/0016-labels-hold-the-roadmap-items-fields.md)), and a person plans them into milestones. No roadmap job reads or writes the [project board](https://github.com/dan-petty/devops-cli/projects); it is a view that filters by those labels and milestones. [`docs/VISION.md`](docs/VISION.md) holds the principles and themes.

---

## Working Documentation

- [AGENTS.md](AGENTS.md) — Single source of truth for AI agents.
- [Knowledge Base](src/devops_cli/ai/knowledge_base/README.md) — Comprehensive technical manual for tools and operational tasks.
- [CHANGELOG.md](CHANGELOG.md) — The changes of each release, which release-please writes.
- [Releases](https://github.com/dan-petty/devops-cli/releases) — The release notes, the wheel and the sdist of each release.
- [VISION.md](docs/VISION.md) — Principles and themes.
- [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — Operational edge cases and intentional design trade-offs.

---

## Command Reference

[`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) lists each command group with its summary, and the command matrix gives the usage and the purpose of each command. Each group has a page in `docs/commands/` with the full text of each command. `devops docs generate` writes these pages from the command tree, and `devops <group> --help` shows the same text.

---

## License

Distributed under the MIT License. See [LICENSE](https://github.com/dan-petty/devops-cli/blob/main/LICENSE) for details.
