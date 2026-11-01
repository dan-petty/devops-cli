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
- **Active SSRF & Egress Guardrails**: Every HTTP client is built by the `devops_cli.http.client` factory. Each client checks the address it dials, at the connect and on every redirect, against its egress level (public, loopback or private). A rebinding DNS answer cannot slip past a check made earlier. Kept pre-flight checks (Qdrant, kubectl manifest apply, container engine endpoint, config init wizard) call `vet_addresses` at their level. Cloud metadata endpoints are refused at every level.
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
- [**Documentation Home Page (`docs/index.md`)**](docs/index.md) — Overview and table of contents for the documentation site.
- [**Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**](docs/ROUTINE_TASKS.md) — Operational task matrix, cadences, execution order, and troubleshooting protocols.
- [**Consolidated CLI Reference (`docs/CLI_REFERENCE.md`)**](docs/CLI_REFERENCE.md) — Full subcommand reference.
- [**Environment Variables Guide (`docs/ENV_VARS.md`)**](docs/ENV_VARS.md) — System and environment settings.
- [**FastMCP Tools Specification (`docs/MCP_TOOLS.md`)**](docs/MCP_TOOLS.md) — Registered MCP tools.
- [**Configuration Reference (`docs/CONFIGURATION.md`)**](docs/CONFIGURATION.md) — Every setting, and the order in which sources set it.
- [**Exit Code & Error Catalog (`docs/ERRORS.md`)**](docs/ERRORS.md) — Error codes, exit codes and their categories.
- [**Telemetry & Tracing Reference (`docs/TELEMETRY.md`)**](docs/TELEMETRY.md) — Metrics, spans and the way they reach Prometheus.
- [**Knowledge Base Catalog (`docs/KNOWLEDGE_BASE.md`)**](docs/KNOWLEDGE_BASE.md) — The manuals that ground the AI commands.
- [**OpenTofu Modules (`tf/README.md`)**](tf/README.md) — Managed Kubernetes cluster modules.
- [**Agent Records (`docs/agent/README.md`)**](docs/agent/README.md) — Compacted records of the early development phases.

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

---

## Local Workstation Model & Security Architecture

1. **Local Workstation Timeouts**: High timeouts (`DEFAULT_HTTP_TIMEOUT_SECONDS = 3600.0` per LLM request, `DEFAULT_REVIEW_TIMEOUT_SECONDS = 1200.0` per review request, unless `ai.timeout` or `ai.tasks.<task>.timeout` sets one; `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) support local LLM inference (CPU/GPU Ollama) and corporate proxies.
2. **Key Material Mounting**: `${localEnv:HOME}/.ssh` is bind-mounted by design into `.devcontainer` for local SSH key generation and 90-day rotation.
3. **SSRF Protections**: Every HTTP client is built by the `devops_cli.http.client` factory (tool downloads, the Tavily search call, Vault, the `k8s://` proxy and cluster-service clients, Loki, the Grafana, Prometheus and Argo CD clients and their token calls, the sandbox probe, the sandbox metrics scrape, Tempo, the LLM client base, the LLM gateway probes and model query, the `devops ai gateway load` query, the embeddings engine, the pydantic-ai models, the pricing fetch, the documentation crawler, the OSV, Shodan InternetDB and Cloudflare Radar lookups, and the Cloudflare API client). Each client has an egress level (`devops_cli.http.egress`) and resolves a host once, at the connect, dialling only the addresses its level admits. Kept pre-flight callers that do not dial through an httpx2 client (qdrant-client, `devops k8s apply` with manifest URLs, Docker engine endpoint) or dial nothing (`devops config init` wizard) call `vet_addresses` directly at their level. The in-process `kubernetes` client (urllib3) is not checked at the connect: it is trusted because its address comes from the operator's kubeconfig or the in-cluster environment. Untrusted URLs (tool downloads, the pages of the documentation crawler), the default pricing registry and the fixed public APIs (OSV, Shodan InternetDB, Cloudflare Radar and the Cloudflare API) are public-only whatever the configuration says. A service URL from the user's own configuration (Ollama, Qdrant, the LLM gateway, a provider's `api_base_url`, `grafana.url`, `prometheus.url`, `argocd.url`) may name loopback, and a private address once `ai.allow_private_network` (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`) is set. Internal infrastructure clients (Vault, the `k8s://` proxy, Loki, the `devops ai gateway connect` probe) reach private addresses. Cloud metadata addresses are refused at every level. Factory clients ignore `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY`.
4. **Workspace Boundary Guards**: Path traversal checks (`_is_safe_workspace_path`) enforce repository boundaries on file commands.
5. **Checksum Verification**: `devops install-tools` installs every tool only from `tools.lock` (`src/devops_cli/tools_lock/`), at an exact version. A binary is checked against the lock's SHA-256 for its platform, a Python tool (Semgrep, Bandit) installs with `uv pip sync --require-hashes` into a virtual environment of its own, and a Node tool (OpenSpec, Dev Containers CLI) installs with `npm ci --ignore-scripts` from a committed `package-lock.json`, which npm checks against the sha512 of every package (`npm` must already be on PATH); a mismatch is refused and the command exits 1. `devops install-tools --check` lists each tool not linked at its locked version.
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

## Complete Command Matrix


<!-- COMMAND_MATRIX_START -->

| Command Group | Subcommand / Usage | Purpose & Features |
|---|---|---|
| [**repos**](docs/commands/repos.md) | `devops repos clone-org [OPTIONS] <org>` | Clone all repos from a GitHub org into `repos/<org>/.`. |
|  | `devops repos clone [OPTIONS] <url>` | Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`). |
|  | `devops repos list [OPTIONS]` | List all cloned repositories. |
|  | `devops repos update [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
|  | `devops repos sync [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
|  | `devops repos worktrees COMMAND [ARGS]...` | Clone, synchronize, and manage organization repositories. |
| [**ssh**](docs/commands/ssh.md) | `devops ssh generate [OPTIONS]` | Generate a new Ed25519 SSH key with prefix and YYYYMMDD date suffix. |
|  | `devops ssh register [OPTIONS]` | Generate, rotate, audit, and register Ed25519 SSH keypairs. |
|  | `devops ssh rotate [OPTIONS]` | Rotate keys older than rotation_days (default 90). |
|  | `devops ssh list [OPTIONS]` | List the managed SSH keys of the project prefix with their age and rotation status. |
|  | `devops ssh audit [OPTIONS]` | List the managed SSH keys of the project prefix with their age and rotation status. |
|  | `devops ssh status [OPTIONS]` | Show the active SSH key and days until rotation. |
| [**branches**](docs/commands/branches.md) | `devops branches update [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches sync [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches jira [OPTIONS] <ticket_id>` | Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]. |
|  | `devops branches list [OPTIONS]` | List branches across all repos. |
|  | `devops branches clean [OPTIONS]` | Delete local branches merged into main/master. |
| [**devcontainer**](docs/commands/devcontainer.md) | `devops devcontainer init [OPTIONS] <repo_path>` | Scaffold .devcontainer/ using the published DevOps CLI devcontainer image. |
|  | `devops devcontainer update [OPTIONS] <repo_path>` | Update the Python image version in an existing devcontainer.json. |
|  | `devops devcontainer validate [OPTIONS]` | Validate .devcontainer/devcontainer.json manifest syntax and configuration schema. |
|  | `devops devcontainer list [OPTIONS]` | List repos with their devcontainer status. |
|  | `devops devcontainer unlock-keyring [OPTIONS]` | Create or unlock the gnome-keyring login keyring that gh, git and devops store secrets in. |
|  | `devops devcontainer post-create [OPTIONS]` | Execute DevContainer post-create setup tasks (history, shell completions, config prep). |
|  | `devops devcontainer post-start [OPTIONS]` | Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync). |
|  | `devops devcontainer run-lifecycle [OPTIONS]` | Run specified DevContainer lifecycle hook tasks natively in Python. |
|  | `devops devcontainer bootstrap-k8s [OPTIONS]` | Execute Minikube cluster startup in the background. |
| [**workspace**](docs/commands/workspace.md) | `devops workspace add [OPTIONS] <repo_path>` | Add a folder to the VS Code workspace file. |
|  | `devops workspace remove [OPTIONS] <repo_path>` | Remove a folder from the VS Code workspace file. |
|  | `devops workspace generate [OPTIONS]` | Regenerate the workspace file from all repos in the repos directory. |
|  | `devops workspace open [OPTIONS]` | Open the workspace in VS Code. |
|  | `devops workspace clean [OPTIONS]` | Clean stale reviews, analysis, logs, traces, benchmarks and cache under the data directory. |
| [**install-tools**](docs/commands/install-tools.md) | `devops install-tools status [OPTIONS]` | Show each tool's locked version and where its command is installed, without a request. |
| [**openspec**](docs/commands/openspec.md) | `devops openspec check` | Run the OpenSpec gate: validate every change and archived change, check the committed skills against a regeneration, render the instructions every agent reads, and find a requirement that two changes rewrite. Exits 1 on any problem. |
|  | `devops openspec regenerate` | Rewrite the committed OpenSpec skills with `openspec update --force` under an isolated configuration, so no developer's own profile decides what is written. |
|  | `devops openspec archive <change>` | Archive a change with `openspec archive <change> --yes`, then run `openspec validate --all --strict`. Both runs use an isolated configuration with telemetry off. The command exits 1 when a run fails. A failed archive skips the validation. |
| [**k8s**](docs/commands/k8s.md) | `devops k8s contexts [OPTIONS]` | List kubeconfig contexts and mark the active one. |
|  | `devops k8s switch-context [OPTIONS] <name>` | Switch active kubeconfig context and ensure cluster is running. |
|  | `devops k8s status [OPTIONS]` | Show node and pod summary for the current context. |
|  | `devops k8s apply [OPTIONS] <path>` | Apply a Kubernetes manifest (delegates to kubectl). |
|  | `devops k8s render [OPTIONS] <path>` | Render Kubernetes manifest templates with domain and variables substituted. |
|  | `devops k8s logs [OPTIONS] <pod> <query_arg>` | Stream pod logs or execute LogQL queries across cluster log streams. |
|  | `devops k8s bootstrap [OPTIONS]` | Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress. |
|  | `devops k8s bootstrap-openwebui [OPTIONS]` | Bootstrap or activate a local administrator account for Open-WebUI. |
|  | `devops k8s bootstrap-mattermost [OPTIONS]` | Bootstrap Mattermost teams, channels, webhooks, and slash commands in Kubernetes. |
|  | `devops k8s deploy-stack [OPTIONS]` | Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize. |
|  | `devops k8s sync-secrets [OPTIONS]` | Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring. |
|  | `devops k8s push-secrets [OPTIONS]` | Write the cluster's Secrets from the OS keyring (workstation keyring → cluster, the reverse of sync-secrets). Adopts live values the keyring lacks, generates the ones nobody types, and never replaces a live value without --rotate. |
|  | `devops k8s run-job [OPTIONS] <args>` | Run a devops command as a Job in namespace devops, from the template of a CronJob with only its arguments changed, follow its log and exit with its exit code. |
|  | `devops k8s configure-urls [OPTIONS]` | Auto-detect Kubernetes stack URLs and update CLI config. |
|  | `devops k8s service-url [OPTIONS] <service>` | Show, or fetch from, a cluster service address that needs no port-forward. |
|  | `devops k8s port-forward [OPTIONS]` | Port-forward k8s monitoring / LLM stack services to localhost ports. |
|  | `devops k8s port-forward-status` | List active background Kubernetes port-forward daemons. |
|  | `devops k8s port-forward-stop [OPTIONS]` | Terminate active background Kubernetes port-forward daemons. |
|  | `devops k8s teardown-stack [OPTIONS]` | Uninstall the k8s infrastructure / LLM stack and delete namespaces. |
|  | `devops k8s rbac-audit [OPTIONS]` | Audit RBAC RoleBindings and ServiceAccounts for overprivileged access. |
|  | `devops k8s lint [OPTIONS] <target>` | Validate K8s manifests and Helm charts using Red Hat Kube-linter. |
|  | `devops k8s audit [OPTIONS]` | Sanitize active K8s/Minikube cluster resource health using Derailed Popeye. |
|  | `devops k8s check-deprecated [OPTIONS] <target>` | Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto. |
|  | `devops k8s image-pins [OPTIONS] <root>` | Render each Argo CD Application of the repository and resolve each image it pins in its
registry, as an anonymous client, without pulling it. Exits 1, before it resolves an image, when
an image has no digest and the latest tag or no tag, unless Image Updater moves it. Exits 1 when
a registry does not hold an image or refuses the read. Docker Hub counts each read of a Docker
Hub image as an anonymous pull, from the allowance of the network's public address, which the
cluster's nodes may share; the CI job `image-pins` runs the check on a pull request that changes
k8s/. |
|  | `devops k8s create-tls-secret [OPTIONS] <secret_name>` | Create or update a kubernetes.io/tls secret from certificate and private key files. |
|  | `devops k8s enable-tls [OPTIONS]` | Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces. |
|  | `devops k8s validate [OPTIONS] <manifest_path>` | Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform. |
|  | `devops k8s validate-policy [OPTIONS] <manifest_path>` | Validate Kubernetes manifests against Kyverno or OPA admission policies. |
|  | `devops k8s stream-logs [OPTIONS] <pod_query>` | Stream logs across multiple pods in parallel using Stern or kubectl. |
|  | `devops k8s diff-helm [OPTIONS] <release_name> <chart_path>` | Preview Kubernetes manifest diffs before executing a Helm upgrade. |
|  | `devops k8s chaos [OPTIONS] <experiment>` | Run resilience and chaos experiments against Kubernetes workloads. |
|  | `devops k8s pods [OPTIONS]` | List running pods with health status, restart counts, and age. |
|  | `devops k8s security-stream [OPTIONS]` | Stream runtime security anomaly events from Kubernetes Falco eBPF probes. |
|  | `devops k8s gpu-matrix [OPTIONS]` | Query traditional homelab GPU matrix and model service alias mappings. |
|  | `devops k8s doctor [OPTIONS]` | Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations. |
|  | `devops k8s tunnel COMMAND [ARGS]...` | Keep the local end of the Kubernetes API route at k8s.\<domain\> running: one 'cloudflared access tcp' forward, for the tunnel kubeconfig context off the home network. |
|  | `devops k8s volume COMMAND [ARGS]...` | Move a local-path claim to a volume on another node, and reclaim orphaned PersistentVolumes. |
| [**kustomize**](docs/commands/kustomize.md) | `devops kustomize build [OPTIONS] <path>` | Build kustomize overlays (delegates to kustomize build). |
|  | `devops kustomize diff [OPTIONS] <path>` | Show a diff of pending changes (delegates to kubectl diff -k). |
|  | `devops kustomize apply [OPTIONS] <path>` | Apply a kustomization (delegates to kubectl apply -k). |
| [**docker**](docs/commands/docker.md) | `devops docker images [OPTIONS]` | List local Docker images. |
|  | `devops docker build [OPTIONS] <context>` | Build a Docker image. |
|  | `devops docker push [OPTIONS] <image>` | Push a Docker image to a registry. |
|  | `devops docker prune [OPTIONS]` | Remove stopped containers, unused networks, dangling images and, with --volumes, unused volumes. |
|  | `devops docker stats [OPTIONS]` | Display live container CPU, memory, and network I/O statistics. |
|  | `devops docker cache [OPTIONS]` | Introspect BuildKit multi-stage layer cache occupancy, reuse, and reclaimable space. |
|  | `devops docker sandbox [OPTIONS] <command>` | Execute workload inside an isolated, disposable Docker container sandbox. |
|  | `devops docker sign [OPTIONS] <image>` | Sign a container image using Sigstore Cosign (keyless or keyed). |
|  | `devops docker verify [OPTIONS] <image>` | Verify container image signature or attestation using Sigstore Cosign. |
| [**grafana**](docs/commands/grafana.md) | `devops grafana search [OPTIONS]` | Search Grafana dashboards and folders by query string. |
|  | `devops grafana datasources [OPTIONS]` | List configured datasources. |
|  | `devops grafana alerts [OPTIONS]` | List alert rules (Grafana 9+ unified alerting). |
|  | `devops grafana dashboards COMMAND [ARGS]...` | Grafana dashboard and alert management. |
| [**prometheus**](docs/commands/prometheus.md) | `devops prometheus query [OPTIONS] <expr>` | Execute an instant PromQL query. |
|  | `devops prometheus query-range [OPTIONS] <expr>` | Execute a range PromQL query and summarise the result. |
|  | `devops prometheus analyze [OPTIONS] <expr>` | Detect anomalies and project the trend of a metric series, computed locally. |
|  | `devops prometheus rules [OPTIONS]` | List Prometheus recording and alerting rules. |
|  | `devops prometheus targets [OPTIONS]` | List active Prometheus scrape targets. |
| [**argo**](docs/commands/argo.md) | `devops argo sync [OPTIONS] <name>` | Synchronize an ArgoCD application (or multi-cluster fleet when --fleet is passed). |
|  | `devops argo cd COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo workflows COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo rollouts COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo fleet COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo gitops COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
| [**config**](docs/commands/config.md) | `devops config show [OPTIONS]` | Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value. |
|  | `devops config get <key>` | Print a single configuration value. |
|  | `devops config set [OPTIONS] <key> <value>` | Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden. |
|  | `devops config unset <key>` | Remove a key from the config file, also a key that stops the settings from loading. |
|  | `devops config init [OPTIONS]` | Interactive first-time setup wizard. |
|  | `devops config env-vars [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config env [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config output [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config auth-headless <key> <token>` | Load secret tokens into ephemeral memory for headless CI environments lacking DBus. |
|  | `devops config audit-stream <destination>` | Stream stored audit records to SIEM destination URL. |
|  | `devops config audit-keys [OPTIONS]` | Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak. |
| [**ci**](docs/commands/ci.md) | `devops ci test [OPTIONS] <paths>` | Run the test suite, or only the tests covering the given source files. |
|  | `devops ci coverage [OPTIONS]` | Run pytest with parallel code coverage analysis over src/. |
|  | `devops ci lint [OPTIONS]` | Run ruff linter across the project, automatically applying fixes by default. |
|  | `devops ci format [OPTIONS]` | Format codebase with ruff format (or verify in check-only mode with --check). |
|  | `devops ci typecheck [OPTIONS]` | Run mypy static type-checker strictly targeting Python 3.14 over src/. |
|  | `devops ci audit [OPTIONS]` | Run uv audit and npm audit to check for known package vulnerabilities. |
|  | `devops ci security [OPTIONS]` | Run bandit static security analysis over src/ at low severity and over tests/ at --severity. |
|  | `devops ci actionlint [OPTIONS]` | Run actionlint to validate GitHub Actions workflows for syntax and schema errors. |
|  | `devops ci docs [OPTIONS]` | Verify (or update with --fix) that documentation is up to date with CLI commands and configuration. |
|  | `devops ci uv-check [OPTIONS]` | Run uv check for fast static type checking and project validation. |
|  | `devops ci lockfile [OPTIONS]` | Verify lockfile consistency and freshness via uv lock --check. |
|  | `devops ci build [OPTIONS]` | Build the wheel and the sdist via uv build. |
|  | `devops ci outdated [OPTIONS]` | Display outdated dependencies and packages via uv tree --outdated. |
|  | `devops ci devcontainer [OPTIONS]` | Validate devcontainer manifest configuration syntax. |
|  | `devops ci deps [OPTIONS]` | Validate dependency hygiene and imports via deptry. |
|  | `devops ci test-settings [OPTIONS]` | Verify test configuration settings and environment variables. |
|  | `devops ci maintain [OPTIONS]` | Run automated toolchain, dependency freshness, and lockfile maintenance checks. |
|  | `devops ci run [OPTIONS]` | Run full CI and return a single pass/fail status. |
|  | `devops ci mutate [OPTIONS] <paths>` | Mutation-test functions with mutmut and show each mutant no test killed; never a gate. |
|  | `devops ci job-time [OPTIONS]` | Fail when the last runs of a CI job took more than the limit on average. Reads the job time of the last completed push runs of a workflow on a branch from GitHub's Actions API. A job that passed, failed or timed out counts, whatever the run concluded. Fails too when fewer runs than asked for could be read. |
|  | `devops ci fail-to-pass [OPTIONS]` | Replay added or modified tests against the merge-base tree to prove a defect fix's tests fail unpatched. |
| [**uv**](docs/commands/uv.md) | `devops uv sync [OPTIONS]` | Sync project dependencies into the virtual environment. |
|  | `devops uv lock [OPTIONS]` | Regenerate the uv lockfile. |
|  | `devops uv python-install [OPTIONS]` | Install project Python version with uv. |
|  | `devops uv run` | Run an arbitrary command using `uv run`. |
| [**scan**](docs/commands/scan.md) | `devops scan trivy [OPTIONS] <target>` | Run Aqua Trivy vulnerability, secret, and misconfiguration scan. |
|  | `devops scan secrets [OPTIONS] <target>` | Run Gitleaks secret pre-filter scan across workspace or targets. |
|  | `devops scan workflows [OPTIONS] <target>` | Audit GitHub Actions workflows with zizmor offline: template injection, unpinned actions
and excessive permissions fail it, and every other finding is shown. |
|  | `devops scan sast [OPTIONS] <target>` | Run static application security testing (SAST) via Semgrep. |
|  | `devops scan complexity [OPTIONS] <target>` | Run AST-based cyclomatic complexity analysis. |
|  | `devops scan sbom [OPTIONS] <target>` | Generate Software Bill of Materials (SBOM) using Trivy (#1439). |
|  | `devops scan aibom [OPTIONS] <target>` | Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates. |
|  | `devops scan fix [OPTIONS] <target>` | Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation. |
|  | `devops scan injection [OPTIONS] <target>` | Scan target files for prompt-injection smuggling vectors and canary tokens. |
|  | `devops scan report [OPTIONS] <target>` | Run every registered scanner and report deduplicated, correlated findings. |
|  | `devops scan sarif [OPTIONS] <document>` | Ingest a SARIF document from any tool and report it in the unified taxonomy. |
| [**ai**](docs/commands/ai.md) | `devops ai config [OPTIONS]` | Show or update AI provider configuration. |
|  | `devops ai models [OPTIONS]` | List available models for the configured provider. |
|  | `devops ai preload [OPTIONS]` | Preload configured model into VRAM across all configured Ollama servers. |
|  | `devops ai test [OPTIONS]` | Send a test prompt to verify AI provider connectivity across configured servers. |
|  | `devops ai prewarm [OPTIONS]` | Prewarm local models into GPU VRAM or evict idle models across cluster nodes. |
|  | `devops ai agents [OPTIONS]` | Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, GEMINI.md, copilot-instructions.md). |
|  | `devops ai chat [OPTIONS]` | Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG). |
|  | `devops ai bundle-models [OPTIONS]` | Bundle Ollama model metadata into tarball for air-gapped DevContainers. |
|  | `devops ai pipeline [OPTIONS] <prompt>` | Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context. |
|  | `devops ai token-count [OPTIONS] <target>` | Calculate exact BPE tokens for text or files using tiktoken context budgeting. |
|  | `devops ai spec [OPTIONS] <spec_path>` | Verify codebase against executable markdown architecture specification contracts. |
|  | `devops ai repomap [OPTIONS]` | Generate compact whole-repository AST symbol and relationship map. |
|  | `devops ai audit-library-usage [OPTIONS]` | Audit workspace code for library API drift and deprecated calls. |
|  | `devops ai pack-context [OPTIONS] <target_path>` | Pack and prune source code context to fit token budget while preserving signatures. |
|  | `devops ai read [OPTIONS] <target_path>` | Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window). |
|  | `devops ai diagram [OPTIONS] <diagram_type>` | Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams. |
|  | `devops ai prompt-eval [OPTIONS]` | Count the review verdicts the feedback dataset records for one producer's findings. |
|  | `devops ai test-gen [OPTIONS] <target_file>` | Generate failing pytest unit test scaffolds for functions or source files. |
|  | `devops ai chaos-model [OPTIONS]` | Model dependency chaos engineering suite simulating provider faults and validating local failovers. |
|  | `devops ai quiesce [OPTIONS]` | Set the constellation quiesce flag with a reason; it stops nothing. |
|  | `devops ai failover [OPTIONS]` | Record a fallback route in the constellation flag; `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic. |
|  | `devops ai resume [OPTIONS]` | Clear the constellation quiesce or failover flag. |
|  | `devops ai constellation [OPTIONS]` | Show the constellation flag: state, reason and recorded fallback route. |
|  | `devops ai review [OPTIONS] COMMAND [ARGS]...` | AI-powered code review and group analysis system. |
|  | `devops ai analyze [OPTIONS] COMMAND [ARGS]...` | Analyze codebase metadata and generate structural outlines. |
|  | `devops ai rag [OPTIONS] COMMAND [ARGS]...` | Manage RAG vector embeddings, indexing, and semantic search (Qdrant). |
|  | `devops ai benchmark [OPTIONS]` | Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks. |
|  | `devops ai cache COMMAND [ARGS]...` | Manage LLM response cache, performance metrics, and warm starting points. |
|  | `devops ai harness COMMAND [ARGS]...` | Manage agent harness slots, sub-agent local offloading, and tiered synthesis. |
|  | `devops ai ingest COMMAND [ARGS]...` | Ingest library API contracts, type stubs, and documentation. |
|  | `devops ai ast COMMAND [ARGS]...` | Tree-Sitter multilingual AST concrete syntax tree parsing and code graph synthesis. |
|  | `devops ai gateway COMMAND [ARGS]...` | LLM Gateway and distributed inference mesh management. |
|  | `devops ai runs COMMAND [ARGS]...` | Benchmark and evaluation runs, kept in the data directory and shared through Valkey. |
|  | `devops ai cost [OPTIONS] COMMAND [ARGS]...` | Track approximate lifetime spend and manage model pricing. |
|  | `devops ai spend [OPTIONS] COMMAND [ARGS]...` | Alias for 'cost' command. |
|  | `devops ai research COMMAND [ARGS]...` | Epistemic research, information foraging, and relational codebase exploration. |
| [**review**](docs/commands/review.md) | `devops review path [OPTIONS] <targets>` | Review source files directly (no git required). |
|  | `devops review branch [OPTIONS] <branch_name>` | Review a git branch diff. |
|  | `devops review pr [OPTIONS] <number>` | Review a GitHub pull request. |
|  | `devops review findings [OPTIONS] <session>` | Inspect structured findings for a review session. |
|  | `devops review verify [OPTIONS] <session>` | Record a person's verdict on a review finding or candidate. |
|  | `devops review intake [OPTIONS] <session>` | Hand the qualifying findings of a session on merged code to roadmap intake, one candidate for each finding. A finding that an issue already carries is left out. |
|  | `devops review stats [OPTIONS]` | Compute and display review accuracy statistics across saved sessions. |
|  | `devops review benchmark [OPTIONS] <targets>` | Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage. |
|  | `devops review score [OPTIONS] <sessions>` | Score saved review sessions against a label file: precision, recall and stability, each with its n. |
|  | `devops review export-feedback [OPTIONS]` | Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads. |
|  | `devops review corpus COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review samples COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review templates COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review rules COMMAND [ARGS]...` | AI-powered code review and security audits. |
| [**mcp**](docs/commands/mcp.md) | `devops mcp serve [OPTIONS]` | Launch FastMCP server to expose devops-cli tools to MCP clients. |
|  | `devops mcp tools` | List all registered FastMCP tools and descriptions. |
|  | `devops mcp export-schemas [OPTIONS]` | Export FastMCP tool JSON schemas and instructions for MCP clients. |
| [**docs**](docs/commands/docs.md) | `devops docs generate [OPTIONS]` | Generate comprehensive Markdown or JSON documentation for all CLI commands and tools. |
|  | `devops docs check [OPTIONS]` | Check that generated documentation and README.md are up to date with codebase. |
|  | `devops docs sync-readme [OPTIONS]` | Synchronize the Complete Command Matrix table in README.md with live CLI commands. |
| [**roadmap**](docs/commands/roadmap.md) | `devops roadmap intake [OPTIONS]` | Turn candidates into items: every open issue with no priority/* label. The model compares each with the items and the issues closed as not planned, but not with an issue that has sub-issues, because its sub-issues deliver it. It names a possible duplicate for a person to close: intake never closes an issue and never drops a candidate. Each gets a type label and a scope label from the Conventional Commit title, a status/new label, Value and Effort labels and a reason comment, then its priority label last, and goes to the backlog. The model picks the type only for a title with no Conventional Commit type. A label a person set stays. Intake sets no milestone: a person plans the milestones, and a milestone an issue has stays. Close an issue as not planned to keep it off the roadmap: devops gh issues close \<number\> --reason not-planned. A candidate an agent files with --title and --body-file is labeled source/agent, and intake files it, a possible duplicate too, unless a run that stopped after filing left an open issue with its title and body, which intake then places; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes. |
|  | `devops roadmap intake-eval [OPTIONS]` | Run the intake duplicate evaluation set against the configured analysis model and print the score of each case. For each case intake plans the candidate in a roadmap that holds the case's item and nothing else, and writes nothing. The run makes one analysis call for each case, one at a time, and no embedding or GitHub request; it reads the type labels from .github/labels.yml of this checkout. It prints whether intake agrees with the person's verdict for each case, and the precision and the recall of the duplicate verdict. It exits 0 when every case ran, and 1 when a case could not run. |
|  | `devops roadmap refine [OPTIONS]` | Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria, using code and documentation. When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it with tools that read the code and, for a public repository with a Firecrawl key, search the web. A design question gets the best-practice option with the options it compared, and only a decision that a person must make waits on a person. The plan says when web search is off. Without --item, refine takes items nearest place first: each open milestone's New items, by due date and then by number, then the backlog's P0 and P1 items, then the backlog's other New items, each place by priority. Only --limit stops a run. The number of Ready items does not stop it. In each open milestone and among the backlog's P0 and P1 items it also takes Ready items it has no record of, and sets one back to New when it finds it not ready. An item that an account other than the owner, a member or a collaborator opened waits on a person, and only --item refines it. An item on which refine wrote 2 comments in the last 24 hours also waits on a person and takes no place under --limit, and only --item refines it until the older comment is 24 hours old. An item refine cannot set to Ready gets one comment with its next step. The step is the questions a person answers, the split a person makes, or the open items it waits on. Refine looks at the item again after a reply, a body edit or the close of those items, or after a commit on the default branch changes a file that the block cites. The report groups every item by its next step. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1. |
|  | `devops roadmap alternatives [OPTIONS]` | Check open items for an open, maintained tool or library that already covers their need, in whole or in part. For each item, one agent run searches the web with Firecrawl and reads the facts of each candidate from GitHub and PyPI: its license, its last activity and whether it is archived. The verdict is covers, partly, none or not-applicable. With --confirm, a check posts one comment, replaces the block `devops-roadmap-alternatives` in the item's body, and records the check in the job record. It changes no label and closes no issue. A person decides what a tool means for the item. The run takes open New and Ready items that a person with write access opened: first the items with no check, lowest number first, then the items whose check is older than roadmap.alternatives.recheck_days or whose text changed since. The check is off, and the plan says why, for a private repository or with no Firecrawl key. An item whose model call fails, whose run stops or whose reply the job refuses is skipped, reported and recorded in its job record, and the others are written. The run takes that item again after roadmap.alternatives.retry_days. The command exits 1 only when it tried items and checked none. |
|  | `devops roadmap stage [OPTIONS]` | Make Ready items Staged: for each item that a label filter names, make the branch \<type\>/\<issue\>-\<slug\> at the fetched default branch, write the OpenSpec change of the item in task groups that each fit the step budget, make one commit as the identity of the session, push it, and open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The branch keeps the type of the issue. The Status of the item stays Ready, and the job does not mark the pull request ready: the Service does, in its row stage_ready, when all checks of the draft have passed. One comment on the issue names the branch, the pull request and the task groups with their measures. The default filter is status=ready: the job takes the Ready items of any type, priority and effort, the highest priority first. The job leaves out an item that is not Ready, an item with the label needs-split, an item that an account without write access opened, an item that depends on an open issue, an item that a pushed branch or a worktree holds, an item whose plan is on the default branch or whose change is archived there, and an item whose text looks like a secret; the plan says why. A task group over the budget goes back to the model once, and a group still over it stops the item. An item whose model call fails is skipped and reported, the others are still staged, and the command then exits 1. Each run also removes the draft and the branch of a closed item when only the identity of the session wrote to them. |
|  | `devops roadmap run [OPTIONS]` | Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every 31 minutes, on a first run, and after an intake that placed a critical fix or a P0 item; the alternatives check is due every 719 minutes and on a first run, and checks at most roadmap.alternatives.limit items. Without --confirm, or with --dry-run, prints the due list and runs nothing. |
|  | `devops roadmap implement [OPTIONS]` | Implement a Staged item, in bounded steps. With --group it runs one task group of the change of an item in the checkout --source: the agent is pydantic-ai's Coder on the model of ai.tasks.implement. Its inputs are the AGENTS.md of the checkout, the sections of the documents that it routes the group to (a test file brings docs/TESTING.md), the item's title, problem and acceptance criteria, the change's proposal, design and tasks, the group, and the files the group names. The command refuses to start when they do not fit the window of the task, or when the checkout has uncommitted changes. The shell of the agent runs only git, uv, ruff and mypy, with a scratch home. When the agent returns, the command runs the verification commands of the group, ruff on the changed Python files, and mypy on the changed files that the type check of devops ci covers (the files under src, with its options), and checks that the agent made no commit, removed or renamed no test that existed at the start of the step, and ticked every task of the group. Before these checks it deletes each new file that git does not ignore, that the group does not name, and that is outside src, tests, docs and openspec, and lists the files in the report. The command writes the tasks file back to its text before the run and keeps only the ticks of the group, so no edit of that file stops the step. An agent that forgets a tick gets one more turn that asks only for the ticks, and that may change only the tasks file. When every check passes, it commits the checkout as '<group title> (#\<item\>)'. Otherwise it resets the checkout to the commit where the step started, reports the step as stopped with the reason and the masked diff of the work it discarded, and exits 1. It writes nothing to GitHub. Without --group it is the job. It takes each Staged or Planned item that a label filter names (default: status=ready, status=planned, effort=low). A Staged item has its staged branch and draft on origin. A Planned item has its change folder on the default branch and no branch: the job makes the branch \<type\>/\<issue\>-\<slug\> there, with the slug of the folder, and opens the draft when the branch first holds a commit. The job rebases the branch, runs a step for each task group that has an unticked task, regenerates the documentation, archives the change, pushes, sets the title and the body of the pull request (the title of the issue, and a body that closes it), watches the checks, runs one fix step for a failed check, and marks the pull request ready. A step that fails stops the item: the job comments why and shows the masked diff of the discarded work, sets the Status to Blocked, and the Service runs the item again only after a comment 'implement: retry' or one time for each new runner image. The job leaves out an item that an agent or a person claimed with a label owner/agent or owner/human. When one claims an item that a running job works on, the job ends it at the next group boundary, with no push and no pull request. The job never merges. --confirm runs steps only when the setting roadmap.implement.in_runner is true, which only the pod of a runner Job sets: the shell of the agent is no security boundary. On a workstation, --item \<n\> --confirm starts that runner Job for the item, with the code of devops k8s run-job --template runner, and follows its log (--no-wait prints the Job's name). It refuses an item that an agent or a person claimed, an item that is neither Ready nor Planned, and a repository that has a runner Job that has not ended. --dry-run --item \<n\> prints the Job and makes no request. |
|  | `devops roadmap explain [OPTIONS] <item>` | Say, for one issue, whether the stage job and the implement job take it. For each job the answer is yes, or no with the reason of the first rule that fails: the issue is closed or is no item, the filter, the rules of the job (the Status, the owner, the stop on record, the plan and the branch), and the limit of a run. The reasons are the texts of the 'Left out' list of stage --plan and implement --plan. The command reads GitHub and git, calls no model and writes nothing. It uses the filter and the limit that the Service uses for each job. A group over the step budget shows only when an earlier run recorded it. |
|  | `devops roadmap inbox [OPTIONS]` | List what waits for a person, each line with its number, its age and the one command or action that clears it. The order is: ready plan pull requests of the jobs (G1), ready implementation pull requests of the jobs (G2), the open release pull request (G3), items in status/blocked with their cause, claims with no activity for 7 days, and labels of .github/labels.yml that the repository lacks. A second list holds the other open pull requests, those of people and agents, with drafts marked. The age is the time since the last update. A draft of a job and a pull request that a runner Job holds are not listed. The command reads the open issues, the open pull requests, the labels and the labels file, and the newest commit of that file when the labels differ. A run sends 5 requests, or 6 when the labels differ, and one more for each 100 open issues and pull requests. It calls no model and writes nothing. It leaves out an image digest that is not rolled yet: run devops argo cd apps status devops. |
|  | `devops roadmap return [OPTIONS] <item>` | Return an item to New with an evidence comment, handing it back to refinement when it cannot be built as specified or needs a refactor beyond its scope. The item gets the label status/new in place of its other status/* label. |
|  | `devops roadmap claim [OPTIONS] <item>` | Claim an item for an agent or a person with the label owner/agent or owner/human. An item has one owner. A person can take an item from the Service. The jobs stage and implement take no item that an agent or a person claimed. |
|  | `devops roadmap release [OPTIONS] <item>` | Release an item: remove its owner/* label, whoever holds it. No job removes the claim of an agent or a person. |
|  | `devops roadmap eval COMMAND [ARGS]...` | Score the plan and implement jobs on a golden set. Each command runs a job's real code on committed cases with a chosen model. It is on demand and no part of devops ci. |
| [**pr**](docs/commands/pr.md) | `devops pr list [OPTIONS]` | List pull requests with base targeting and review status. |
|  | `devops pr view [OPTIONS] <number>` | View details of a pull request. |
|  | `devops pr checks [OPTIONS] <number>` | Check remote CI quality gate status on a pull request. |
|  | `devops pr wait [OPTIONS] <number>` | Wait until the checks of a PR settle, then name every blocker of its merge. |
|  | `devops pr monitor [OPTIONS] <number>` | Wait until the checks of a PR settle, then name every blocker of its merge. |
|  | `devops pr edit [OPTIONS] <number>` | Edit pull request base branch, title, body, or milestone. |
|  | `devops pr create [OPTIONS]` | Open a draft pull request, into the default branch unless --base names another. |
|  | `devops pr ready [OPTIONS] <number>` | Mark a draft pull request as ready for review once its checks pass. |
|  | `devops pr diff [OPTIONS] <number>` | View diff of a pull request. |
|  | `devops pr close [OPTIONS] <number>` | Close a pull request. |
|  | `devops pr check-readiness [OPTIONS] <number>` | Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding. |
|  | `devops pr update [OPTIONS] <number>` | Update pull request branch with latest commits from its base branch. |
|  | `devops pr hardening-report [OPTIONS]` | Audit merged defect pull requests for guardrail additions to declared hardening surfaces. |
|  | `devops pr threads COMMAND [ARGS]...` | GitHub Pull Request workflows and reviews. |
| [**gh**](docs/commands/gh.md) | `devops gh api [OPTIONS] <endpoint>` | Execute a GitHub API request with quota-derived spacing, rate-limit backoff, and optional caching. |
|  | `devops gh rate-limit [OPTIONS]` | Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns. |
|  | `devops gh status [OPTIONS]` | Display GitHub published operational status, key components, and active incidents. |
|  | `devops gh metrics [OPTIONS]` | Display comprehensive project metrics including release frequency, PRs, commits, CI pass rates, milestones, and roadmap Items. |
|  | `devops gh labels COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh milestones COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh project COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh views COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh pages COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh issues COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh runs COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh branch-protection COMMAND [ARGS]...` | Manage classic branch protection policies; does not cover rulesets. |
|  | `devops gh secrets COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh pr COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
| [**tf**](docs/commands/tf.md) | `devops tf init [OPTIONS] <directory>` | Initialize an OpenTofu working directory. |
|  | `devops tf plan [OPTIONS] <directory>` | Generate and show an OpenTofu execution plan. |
|  | `devops tf apply [OPTIONS] <directory>` | Create or update OpenTofu infrastructure. |
|  | `devops tf destroy [OPTIONS] <directory>` | Destroy OpenTofu-managed infrastructure. |
|  | `devops tf output [OPTIONS] <directory>` | Read an output variable from the OpenTofu state. |
|  | `devops tf validate [OPTIONS] <directory>` | Validate the OpenTofu configuration files in a directory. |
|  | `devops tf fmt [OPTIONS] <directory>` | Rewrites OpenTofu configuration files to canonical format. |
|  | `devops tf status <directory>` | Show OpenTofu directory state, initialization status, and provider plugins. |
|  | `devops tf graph [OPTIONS] <directory>` | Inspect the in-memory resource dependency graph and blast radius. |
|  | `devops tf drift [OPTIONS] <directory>` | Compare declared configuration against recorded state. |
|  | `devops tf deploy-cloud [OPTIONS]` | Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP. |
|  | `devops tf lint [OPTIONS] <directory>` | Run TFLint static analysis on Terraform/OpenTofu configurations. |
|  | `devops tf notify-plan [OPTIONS]` | Format and post structured, collapsible OpenTofu/Terraform plan diffs to PR comments. |
|  | `devops tf cost COMMAND [ARGS]...` | OpenTofu and Terraform Infrastructure-as-Code operations. |
| [**tls**](docs/commands/tls.md) | `devops tls ca [OPTIONS]` | Generate a self-signed Root Certificate Authority (CA) key pair. |
|  | `devops tls cert [OPTIONS]` | Generate an X.509 TLS certificate signed by local CA or self-signed. |
|  | `devops tls homelab [OPTIONS]` | Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert). |
|  | `devops tls inspect <cert_path>` | Inspect and display metadata of an X.509 certificate. |
|  | `devops tls verify [OPTIONS] <cert_path>` | Verify an X.509 certificate cryptographic chain against a CA certificate. |
|  | `devops tls enable-k8s [OPTIONS]` | Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces. |
| [**telemetry**](docs/commands/telemetry.md) | `devops telemetry status [OPTIONS]` | Check OpenTelemetry collector health, Tempo endpoint, and trace propagation status. |
|  | `devops telemetry connect [OPTIONS]` | Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there. |
|  | `devops telemetry logfire [OPTIONS]` | Display Logfire structured observability bridge status and token metrics. |
|  | `devops telemetry test [OPTIONS]` | Emit a test OpenTelemetry trace span and metric to the configured collector. |
|  | `devops telemetry profile [OPTIONS] <command>` | Run a devops-cli command, or name a trace, and show its span waterfall as Tempo recorded it. |
|  | `devops telemetry open-ui` | Print and show the Tempo HTTP API endpoint for inspecting traces. |
|  | `devops telemetry semconv COMMAND [ARGS]...` | The GenAI semantic conventions that LLM span attributes are checked against. |
| [**cloudflare**](docs/commands/cloudflare.md) | `devops cloudflare status [OPTIONS]` | Verify Cloudflare API token authentication and inspect zone status. |
|  | `devops cloudflare service-status [OPTIONS]` | Display Cloudflare published operational status, key components, and active incidents. |
|  | `devops cloudflare dns COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
|  | `devops cloudflare tunnel COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
|  | `devops cloudflare access COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
| [**serve**](docs/commands/serve.md) | `devops serve [OPTIONS]` | FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics. |
| [**test**](docs/commands/test.md) | `devops test run [OPTIONS] <target>` | Execute pytest test suite with optional git-diff aware test selection. |
|  | `devops test load [OPTIONS] <script_path>` | Execute developer-centric load, spike, and latency tests against services using k6. |
|  | `devops test sandbox [OPTIONS] <command>` | Execute test command inside an isolated, disposable Docker container sandbox. |
|  | `devops test profile-memory [OPTIONS] <target>` | Deterministic async memory and connection pool profiler using tracemalloc. |
| [**pipeline**](docs/commands/pipeline.md) | `devops pipeline [OPTIONS] <pipeline_path>` | Execute reproducible, containerized developer pipelines with Dagger. |
| [**vault**](docs/commands/vault.md) | `devops vault status [OPTIONS]` | Inspect HashiCorp Vault cluster health and initialization status. |
|  | `devops vault get [OPTIONS] <path>` | Fetch a secret from Vault, or from the OS keyring when Vault cannot answer. |
|  | `devops vault set [OPTIONS] <path> <key_values>` | Store secret key-value pairs in HashiCorp Vault KV-v2 engine. |
|  | `devops vault sync [OPTIONS] <path>` | Synchronize secrets from Vault into OS Keyring for offline/local CLI operations. |
|  | `devops vault login [OPTIONS]` | Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount. |
|  | `devops vault logout [OPTIONS]` | Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it. |
|  | `devops vault leases [OPTIONS]` | Revoke a single Vault dynamic secret lease by id. |
|  | `devops vault audit [OPTIONS]` | Show which provider satisfied each credential lookup in this session. |
| [**valkey**](docs/commands/valkey.md) | `devops valkey ping [OPTIONS]` | Test connection and measure round-trip latency to the Valkey server. |
|  | `devops valkey info [OPTIONS]` | Inspect server configuration, memory allocation, and operational metrics. |
|  | `devops valkey stats [OPTIONS]` | Display quick diagnostic summary of server health, memory, and keys. |
|  | `devops valkey keys [OPTIONS] <pattern>` | List keys matching a glob pattern. |
|  | `devops valkey get [OPTIONS] <key>` | Retrieve string value stored at key. |
|  | `devops valkey set [OPTIONS] <key> <value>` | Set string value of key with optional expiration TTL. |
|  | `devops valkey flush [OPTIONS]` | Flush and purge keys from current or all databases. |
|  | `devops valkey backup [OPTIONS]` | Trigger background RDB persistence snapshot (BGSAVE). |
|  | `devops valkey cli [OPTIONS] <command_args>` | Execute raw Valkey commands directly against the server. |
| [**sandbox**](docs/commands/sandbox.md) | `devops sandbox deploy [OPTIONS] <command>` | Deploy an isolated background container sandbox with security containment. |
|  | `devops sandbox status [OPTIONS] <instance_id>` | Inspect status of deployed sandbox containers. |
|  | `devops sandbox stop [OPTIONS] <instance_id>` | Gracefully stop and tear down a sandbox container. |
|  | `devops sandbox exec [OPTIONS] <instance_id> <command>` | Execute a command inside an active sandbox container. |
|  | `devops sandbox probe [OPTIONS] <identifier>` | Probe endpoint readiness and service health across network protocols. |
|  | `devops sandbox metrics [OPTIONS] <identifier>` | Capture real-time cgroup v2 metrics and scrape Prometheus application metrics. |
|  | `devops sandbox traces [OPTIONS] <identifier>` | Visualize distributed trace waterfall and cross-service latency for sandbox workloads. |
|  | `devops sandbox logs [OPTIONS] <identifier>` | Stream stdout/stderr container logs with automated panic and crash detection. |
|  | `devops sandbox network-policy [OPTIONS]` | Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation. |
| [**dashboard**](docs/commands/dashboard.md) | `devops dashboard [OPTIONS]` | Interactive terminal UI dashboard for workstation situational awareness. |
| [**tui**](docs/commands/tui.md) | `devops tui [OPTIONS]` | Interactive terminal UI dashboard for workstation situational awareness. |
| [**status**](docs/commands/status.md) | `devops status [OPTIONS]` | Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare) |
| [**survey**](docs/commands/survey.md) | `devops survey [OPTIONS]` | Outward-facing capability and upstream maturity survey. |
| [**format**](docs/commands/format.md) | `devops format [OPTIONS]` | Format codebase with ruff format (or verify in check-only mode with --check). |
| [**lint**](docs/commands/lint.md) | `devops lint [OPTIONS]` | Run ruff linter across the project, automatically applying fixes by default. |

<!-- COMMAND_MATRIX_END -->

---

## License

Distributed under the MIT License. See [LICENSE](https://github.com/dan-petty/devops-cli/blob/main/LICENSE) for details.
