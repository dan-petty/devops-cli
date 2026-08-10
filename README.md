# devops-cli — Workstation DevOps CLI & Multi-Persona AI Code Reviewer

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DevContainer Native](https://img.shields.io/badge/DevContainer-Native-green.svg)](.devcontainer/devcontainer.json)

**`devops-cli`** is a workstation CLI designed for DevOps Engineers. Running inside local Dev Containers, it combines multi-repository infrastructure automation (Git, Kubernetes, ArgoCD, Grafana, Prometheus, SSH) with multi-persona **Agentic LLM code reviews**, OS keyring secret isolation, and human-in-the-loop finding verification.

---

## Key Features

- **Multi-Persona AI Code Reviews (`devops review`)**: Run automated, paginated reviews across Git branches, GitHub Pull Requests, or local paths with domain-specialized AI personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`).
- **Finding Verification & Invalidation Loop**: Inspect findings (`devops review findings`), mark false-positives (`devops review verify`), and track persona accuracy metrics (`devops review stats`).
- **Zero-Plaintext Secret Isolation**: Sensitive API credentials (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the OS Keyring via `keyring`.
- **SSRF & Network Egress Safeguards**: Strict validation (`devops_cli.http.validate_service_url`) blocks automated connections to internal/private IP targets unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set explicitly.
- **Automated Infrastructure Commands**:
  - `devops repos`: Multi-repo clone, sync, status, and branch operations.
  - `devops ssh`: Generation, auditing, and 90-day rotation of ED25519 SSH keys.
  - `devops k8s`: Pod status, namespace filtering, and container log streaming with RFC 1123 argument validation.
  - `devops argo`: ArgoCD app sync, status, and Rollout/Workflow operations.
  - `devops grafana` / `devops prometheus`: Dashboard rendering, datasource checks, and PromQL execution.
  - `devops docker`: Workstation image pruning, system cleanup, and container stats.

---

## Quick Start & Installation

### 1. Requirements & Dev Container Setup
`devops-cli` is built to run **inside the provided Dev Container** on your local workstation.

```bash
# Clone the repository and open in VS Code / GitHub Codespaces
git clone https://github.com/your-org/devops-cli.git
cd devops-cli

# Inside the devcontainer, sync Python 3.14 dependencies:
uv sync
```

### 2. Configure Credentials (OS Keyring)
Secrets are stored in the OS keyring and never in environment variables or config files:

```bash
# Set your GitHub token in the OS Keyring
devops config set github.token "ghp_your_personal_access_token"

# Configure AI Review Provider (ollama, claude, copilot, or openai)
devops ai config --provider claude

# Set AI API Key (for Claude or OpenAI-compatible providers)
devops config set ai.api_key "sk-ant-..."

# Verify AI LLM connectivity
devops ai test
```

---

## Command Reference Matrix

| Command Group | Subcommand / Usage | Purpose & Notes |
|---|---|---|
| **AI Reviews** | `devops review branch [<branch>] [--base main] [--persona <p>]` | Review git diff against base branch using AI personas |
| | `devops review pr <number> [--post]` | Review GitHub PR; optionally post summary as PR comment |
| | `devops review path [<target>] [--pattern <glob>]` | Review local files respecting `.gitignore` exclusions |
| | `devops review findings [<session>] [--unverified\|--verified\|--invalidated]` | Inspect structured review findings for a session |
| | `devops review verify <session> --index <N> --status <status> [--reason "..."]` | Validate or invalidate a finding and record human feedback |
| | `devops review stats` | View accuracy metrics and false-positive rates per persona |
| **Repos** | `devops repos clone --org <org>` | Clone all repositories in a GitHub organization |
| | `devops repos sync [--all]` | Fetch and pull latest tracking branches across repos |
| | `devops repos status` | Display uncommitted changes and branch drift across workspace |
| **SSH Keys** | `devops ssh generate [--email <email>]` | Generate ED25519 SSH keypair (`~/.ssh/id_ed25519-YYYYMMM[DD]`) |
| | `devops ssh rotate` | Rotate SSH keys older than 90 days and register with GitHub |
| | `devops ssh audit` | Audit SSH key expiration dates and key file permissions |
| **Kubernetes** | `devops k8s pods [--namespace <ns>]` | List pod status with label filtering and sanitization |
| | `devops k8s logs <pod> --container <c> [--namespace <ns>]` | Stream container logs safely |
| **ArgoCD** | `devops argo status --app <app>` | Check ArgoCD application sync and health status |
| | `devops argo sync --app <app>` | Trigger ArgoCD application sync operation |
| **Grafana** | `devops grafana search [--query <q>]` | Search Grafana dashboards by tag or query |
| **Prometheus**| `devops prometheus query "<promql>"` | Execute PromQL query against Prometheus endpoint |
| **Docker** | `devops docker prune` | Prune dangling Docker containers, networks, and volumes |
| **CI / Quality**| `devops ci` | Run full quality gate (`pytest`, `ruff check`, `ruff format`, `mypy`) |

---

## AI Review Engine & Personas

`devops-cli` executes multi-segment, paginated code reviews using specialized reviewer personas:

```
                          ┌──────────────────────────┐
                          │   Target Code / Diff     │
                          └────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │  Diff Chunking & Meta     │
                         └─────────────┬─────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
  ┌────────▼────────┐         ┌────────▼────────┐         ┌────────▼────────┐
  │   DevSecOps     │         │   Architect     │         │   Compliance    │
  │   Security      │         │   Design & DDD  │         │   NIST/PCI/SOC  │
  └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │  Synthesis & Finding      │
                         │     Deduplication         │
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │   .data/reviews/<session> │
                         │      summary.md           │
                         │      findings.json        │
                         └───────────────────────────┘
```

### Reviewer Personas

- **DevSecOps (`--persona devsecops`)**: Focuses on OWASP Top 10, secret leaks, dependency vulnerabilities, supply chain risks, Dockerfile security, and IaC misconfigurations.
- **Architect (`--persona architect`)**: Focuses on SOLID principles, clean architecture, microservice coupling, observability, API contracts, and scalability.
- **Project Manager (`--persona pm`)**: Focuses on scope risk, breaking changes, test coverage adequacy, deployment rollback steps, and actionable ticket items.
- **Auditor (`--persona auditor`)**: Evaluates code against regulatory control frameworks (NIST SP 800-53, PCI-DSS v4.0, SOC 2 Type II) and cites exact control IDs.
- **QA / Senior Test Engineer (`--persona qa`)**: Evaluates regression risk, test coverage gaps, edge cases, and provides concrete pytest code skeletons.

---

## Strategic Prioritization (Value vs. Effort)

`devops-cli` follows a strict value-versus-effort framework to prioritize ongoing development:

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | RFC 1123 Namespace & Input Sanitization | High | Low | ✅ Completed |
| | Human Finding Invalidation & Stats CLI | High | Low | ✅ Completed |
| | Pydantic Schema Model Unification | High | Low | ✅ Completed |
| **Strategic Investments** | Line-Level GitHub PR Inline Comments | High | High | 🔄 Short-Term (Q3 2026) |
| | Human Invalidation Feedback Dataset Exporter | High | High | 🔄 Short-Term (Q3 2026) |
| | Custom Team Persona Prompt Overrides | High | Medium | 🔄 Short-Term (Q3 2026) |
| **Fill-ins** | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Fallback Auth | Medium | Medium | 🔄 Mid-Term (Q4 2026) |
| **De-prioritized** | Full Bare-Metal OS Install Installers | Low | High | ❌ Rejected (Devcontainer native) |

---

## Security & Compliance Architecture

1. **Zero Plaintext Secrets**: Secrets are read exclusively from the OS Keyring. Environment variable fallbacks for secret tokens are rejected to prevent accidental CI log exposure.
2. **SSRF Mitigation**: `devops_cli.http.validation.validate_service_url` validates all external service targets and blocks non-public IPs unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
3. **Intentional DevContainer Mounts**: The local workstation host's `~/.ssh` directory is bind-mounted by design to enable SSH key generation and rotation without agent forwarding complexities.
4. **Binary SHA-256 Verification**: `devops install-tools` verifies SHA-256 checksums against official release checksum files before writing binaries to disk.

---

## Working Documentation

- [Canonical Agent Instructions](AGENTS.md): Single source of truth for coding AI agents.
- [Project Roadmap](docs/ROADMAP.md): Vision, core principles, and phased milestones.
- [Pending Features & Proposals](docs/PENDING_FEATURES.md): Active design proposals and feature specifications.
- [Known Issues & Trade-offs](docs/KNOWN_ISSUES.md): Operational edge cases and intentional design trade-offs.

---

## License

Distributed under the MIT License. See `LICENSE` for details.
