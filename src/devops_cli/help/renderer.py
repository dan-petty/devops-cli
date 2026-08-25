"""Fast-path help renderer for devops CLI and subcommands."""

from __future__ import annotations

import sys
from typing import Final

from devops_cli import __version__

# Root CLI Help
_ROOT_HELP: Final[str] = """
 Usage: devops [OPTIONS] COMMAND [ARGS]...

 DevOps CLI — manage repos, SSH keys, Kubernetes, and more.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version             -v        Show version and exit.                                                    │
│ --dry-run                       Show debug output of commands and AI requests without executing delegated │
│                                 subcommands or external write actions.                                    │
│ --install-completion            Install completion for the current shell.                                 │
│ --show-completion               Show completion for the current shell, to copy it or customize the        │
│                                 installation.                                                             │
│ --help                -h        Show this message and exit.                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ repos          Clone and manage repositories.                                                             │
│ ssh            SSH key generation, rotation, and GitHub registration.                                     │
│ branches       Branch management and Jira workflows.                                                     │
│ devcontainer   Manage devcontainer configurations.                                                        │
│ workspace      Manage VS Code workspace files.                                                            │
│ install-tools  Install DevOps tool binaries.                                                             │
│ k8s            Kubernetes resource management.                                                            │
│ kustomize      Kustomize operations.                                                                      │
│ docker         Docker image management.                                                                   │
│ grafana        Grafana dashboard and alert management.                                                    │
│ prometheus     Prometheus query and rule management.                                                      │
│ argo           Argo CD, Workflows, and Rollouts management.                                               │
│ config         Manage devops-cli configuration.                                                           │
│ ci             Run tests, linting, formatting, and type-checks.                                           │
│ uv             Run uv commands through devops.                                                            │
│ scan           Security, vulnerability, secret, and IaC scanner.                                          │
│ ai             Configure and test AI providers.                                                           │
│ review         AI-powered code reviews using expert personas.                                             │
│ mcp            FastMCP server for Model Context Protocol integration.                                     │
│ docs           Generate and validate CLI and API documentation.                                           │
│ release        Manage release cycles, version bumping, changelogs, and release verification.              │
│ pr             Manage GitHub pull requests and base branch targeting.                                     │
│ tf             OpenTofu and Terraform Infrastructure-as-Code operations.                                  │
│ tls            X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.        │
│ telemetry      OpenTelemetry observability, tracing, and metrics management.                              │
│ serve          FastAPI REST and OpenAPI service engine.                                                   │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
"""

# Subcommand Help Templates
_SUBCOMMAND_HELPS: Final[dict[str, str]] = {
    "ai": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot).

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --explain             -e        Explain AI agent workflows, FastMCP tools, RAG terminology, and    │
│                                 metrics                                                            │
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ config         Show or update AI provider configuration.                                           │
│ models         List available models for the configured provider.                                  │
│ preload        Preload configured model into VRAM across all configured Ollama servers.            │
│ test           Send a test prompt to verify AI provider connectivity across configured servers.    │
│ agents         Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md,                         │
│                copilot-instructions.md).                                                           │
│ chat           Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming,   │
│                RAG).                                                                               │
│ bundle-models  Bundle Ollama model metadata into tarball for air-gapped DevContainers.             │
│ pipeline       Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.       │
│ token-count    Calculate exact BPE tokens for text or files using tiktoken context budgeting.      │
│ route          Evaluate task complexity and determine the optimal LLM provider and model route.    │
│ review         AI-powered multi-persona code review system.                                        │
│ analyze        Analyze codebase metadata and generate structural outlines.                         │
│ rag            Manage RAG vector embeddings, indexing, and semantic search (Qdrant).               │
│ benchmark      Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.   │
│ cache          Manage LLM response cache, performance metrics, and warm starting points.           │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "argo": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Argo CD, Workflows, and Rollouts management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ cd         ArgoCD application management.                                                          │
│ workflows  Argo Workflows management.                                                              │
│ rollouts   Argo Rollouts management.                                                               │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "branches": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Branch management and Jira workflows.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ update  Fetch and pull tracking branches across all repos.                                         │
│ sync    Fetch and pull tracking branches across all repos.                                         │
│ jira    Create a feature branch for a Jira ticket: feature/PROJ-123[-slug].                        │
│ list    List branches across all repos.                                                            │
│ clean   Delete local branches merged into main/master.                                             │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "ci": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Run tests, linting, formatting, and type-checks.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ test        Run the pytest test suite in parallel leveraging all CPU cores.                        │
│ coverage    Run pytest with parallel code coverage analysis over src/.                             │
│ lint        Run ruff linter across the project.                                                    │
│ format      Check (or apply) code formatting with ruff format.                                     │
│ typecheck   Run mypy static type-checker strictly targeting Python 3.14 over src/.                 │
│ audit       Run uv audit to check for known package vulnerabilities.                               │
│ security    Run bandit static security vulnerability analysis over src/.                           │
│ actionlint  Run actionlint to validate GitHub Actions workflows for syntax and schema errors.      │
│ docs        Verify that documentation is up to date with CLI commands and configuration.           │
│ run         Run full CI and return a single pass/fail status.                                      │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "config": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Manage devops-cli configuration.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                            │
│ --show-completion             Show completion for the current shell, to copy it or customize the   │
│                               installation.                                                        │
│ --help                        Show this message and exit.                                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ show           Print all configuration values, masking secrets.                                    │
│ get            Print a single configuration value.                                                 │
│ set            Set a configuration value. Tokens are stored in the OS keyring.                     │
│ init           Interactive first-time setup wizard.                                                │
│ env-vars       Output environment variables available for devops-cli configuration.                │
│ env            Output environment variables available for devops-cli configuration.                │
│ output         Output environment variables available for devops-cli configuration.                │
│ auth-headless  Load secret tokens into ephemeral memory for headless CI environments lacking DBus. │
│ audit-stream   Stream stored audit records to SIEM destination URL.                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "devcontainer": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Manage devcontainer configurations.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ init           Scaffold .devcontainer/ using the published DevOps CLI devcontainer image.          │
│ update         Update the Python image version in an existing devcontainer.json.                   │
│ validate       Validate .devcontainer/devcontainer.json manifest syntax and configuration schema.  │
│ list           List repos with their devcontainer status.                                          │
│ post-create    Execute DevContainer post-create setup tasks (history, shell completions, config    │
│                prep).                                                                              │
│ post-start     Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP      │
│                sync).                                                                              │
│ run-lifecycle  Run specified DevContainer lifecycle hook tasks natively in Python.                 │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "docker": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Docker image management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ images          List local Docker images.                                                          │
│ build           Build a Docker image.                                                              │
│ push            Push a Docker image to a registry.                                                 │
│ prune           Remove unused containers, images, and networks.                                    │
│ analyze-layers  Analyze container image layer efficiency and wasted space using Dive.              │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "docs": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Generate and validate CLI and architecture documentation.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ generate     Generate comprehensive Markdown or JSON documentation for all CLI commands and tools. │
│ check        Check that generated documentation and README.md are up to date with codebase.        │
│ sync-readme  Synchronize the Complete Command Matrix table in README.md with live CLI commands.    │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "grafana": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Grafana dashboard and alert management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ search       Search Grafana dashboards and folders by query string.                                │
│ datasources  List configured datasources.                                                          │
│ alerts       List alert rules (Grafana 9+ unified alerting).                                       │
│ dashboards   Manage Grafana dashboards.                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "install-tools": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Install and manage DevOps tool binaries.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --tool                -t      <str>   Install a specific tool                                      │
│ --version                     <str>   Specific version, e.g. v1.30.0                               │
│ --target-dir          -d      <path>  [default: /home/vscode/.local/bin]                           │
│ --install-completion                  Install completion for the current shell.                    │
│ --show-completion                     Show completion for the current shell, to copy it or         │
│                                       customize the installation.                                  │
│ --help                -h              Show this message and exit.                                  │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ status  Show installation status and versions for all managed tools.                               │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "k8s": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Kubernetes resource management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ contexts           List kubeconfig contexts and mark the active one.                               │
│ switch-context     Switch active kubeconfig context.                                               │
│ status             Show node and pod summary for the current context.                              │
│ apply              Apply a Kubernetes manifest (delegates to kubectl).                             │
│ logs               Stream pod logs (delegates to kubectl).                                         │
│ bootstrap          Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack.      │
│ deploy-stack       Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to           │
│                    Kubernetes.                                                                     │
│ configure-urls     Auto-detect Kubernetes stack URLs and update CLI config.                        │
│ port-forward       Port-forward k8s monitoring / LLM stack services to localhost ports and update  │
│                    CLI config.                                                                     │
│ teardown-stack     Uninstall the k8s infrastructure / LLM stack and delete namespaces.             │
│ rbac-audit         Audit RBAC RoleBindings and ServiceAccounts for overprivileged access.          │
│ lint               Validate K8s manifests and Helm charts using Red Hat Kube-linter.               │
│ audit              Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.     │
│ check-deprecated   Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto.   │
│ create-tls-secret  Create or update a kubernetes.io/tls secret from certificate and private key    │
│                    files.                                                                          │
│ enable-tls         Generate Homelab certificates and apply TLS secrets across Kubernetes cluster   │
│                    namespaces.                                                                     │
│ validate           Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform.   │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "kustomize": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Kustomize build and apply operations.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ build  Build kustomize overlays (delegates to kustomize build).                                    │
│ diff   Show a diff of pending changes (delegates to kubectl diff -k).                              │
│ apply  Apply a kustomization (delegates to kubectl apply -k).                                      │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "mcp": """

 Usage: mcp [OPTIONS] COMMAND [ARGS]...

 FastMCP server and Model Context Protocol integrations.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ serve  Launch FastMCP server to expose devops-cli tools to MCP clients.                            │
│ tools  List all registered FastMCP tools and descriptions.                                         │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "pr": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Manage GitHub pull requests, base branch targeting, and review gates.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ list    List pull requests with base targeting and review status.                                  │
│ view    View details of a pull request.                                                            │
│ checks  Check remote CI quality gate status on a pull request.                                     │
│ edit    Edit pull request base branch, title, or body.                                             │
│ create  Create a pull request with automatic release branch target validation.                     │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "prometheus": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Prometheus query and rule management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ query        Execute an instant PromQL query.                                                      │
│ query-range  Execute a range PromQL query and summarise the result.                                │
│ rules        List Prometheus recording and alerting rules.                                         │
│ targets      List active Prometheus scrape targets.                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "release": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Manage release cycles, version bumping, changelogs, and release verification.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ status   Display current release status, versions, tags, changelog, and docs state.                │
│ prepare  Bump version across pyproject.toml and source, update changelog, and sync docs.           │
│ pr       Create release branch, commit version bumps, and open a GitHub Release Pull Request.      │
│ check    Verify release readiness (version consistency, docs freshness, and CI quality gates).     │
│ notes    Print markdown release notes for a specified or current release version.                  │
│ tag      Create release commit and annotated git tag.                                              │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "repos": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Clone and manage repositories.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ clone-org  Clone all repos from a GitHub org into repos/<org>/.                                    │
│ clone      Clone an individual repository into repos/_standalone/<name>/.                          │
│ list       List all cloned repositories.                                                           │
│ update     Fetch (and optionally pull) all tracking branches across repos.                         │
│ sync       Fetch (and optionally pull) all tracking branches across repos.                         │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "review": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 AI Code Review across branches, paths, and pull requests.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --explain             -e        Explain code review personas, severity levels, and terminology     │
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ path             Review source files directly (no git required).                                   │
│ branch           Review a git branch diff with one or all AI personas.                             │
│ pr               Review a GitHub pull request with one or all AI personas.                         │
│ findings         Inspect structured findings for a review session.                                 │
│ verify           Validate or invalidate a review finding, persisting feedback reasons.             │
│ stats            Compute and display review accuracy statistics across saved sessions.             │
│ export-feedback  Export review findings into a JSONL benchmark dataset for prompt tuning and       │
│                  fine-tuning.                                                                      │
│ apply-patch      Apply suggested LLM code fix for a verified finding (v0.1.3).                     │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "scan": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Security, vulnerability, secret, and AST scanner (Trivy, Semgrep, Gitleaks).

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --dry-run                       Simulate security scan execution.                                  │
│ --json                          Output raw findings as JSON                                        │
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ trivy     Run Aqua Trivy vulnerability, secret, and misconfiguration scan.                         │
│ secrets   Run Gitleaks secret pre-filter scan across workspace or targets.                         │
│ gitleaks  Alias for devops scan secrets.                                                           │
│ semgrep   Run Semgrep multilingual static AST pattern matching scan.                               │
│ sast      Run static application security testing (SAST) via Semgrep.                              │
│ checkov   Run Checkov Infrastructure-as-Code (IaC) compliance scanner.                             │
│ iac       Run Checkov IaC static policy and security compliance scan.                              │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "serve": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --host                -h               <str>  Network interface host to bind the HTTP server.      │
│                                               [default: 127.0.0.1]                                 │
│ --port                -p               <int>  TCP port to listen on. [default: 8000]               │
│ --reload              -r                      Enable auto-reload on code changes (development      │
│                                               mode).                                               │
│ --workers             -w               <int>  Number of worker processes. [default: 1]             │
│ --log-level           -l               <str>  Logging level (debug, info, warning, error).         │
│                                               [default: info]                                      │
│ --docs                    --no-docs           Enable or disable Swagger UI (/docs) and ReDoc       │
│                                               (/redoc).                                            │
│                                               [default: docs]                                      │
│ --install-completion                          Install completion for the current shell.            │
│ --show-completion                             Show completion for the current shell, to copy it or │
│                                               customize the installation.                          │
│ --help                                        Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "ssh": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 SSH key generation, rotation, and GitHub registration.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ generate  Generate a new Ed25519 SSH key with today's date suffix.                                 │
│ register                                                                                           │
│ rotate    Rotate keys older than rotation_days (default 90).                                       │
│ list      List all managed SSH keys with their age and rotation status.                            │
│ audit     List all managed SSH keys with their age and rotation status.                            │
│ status    Show the active SSH key and days until rotation.                                         │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "telemetry": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 OpenTelemetry observability, tracing, and metrics management.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ status   Check OpenTelemetry collector health, Jaeger endpoint, and trace propagation status.      │
│ test     Emit a test OpenTelemetry trace span and metric to the configured collector.              │
│ open-ui  Print and show the Jaeger Query UI endpoint for inspecting traces.                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "tf": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 OpenTofu and Terraform Infrastructure-as-Code operations.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ init          Initialize an OpenTofu working directory.                                            │
│ plan          Generate and show an OpenTofu execution plan.                                        │
│ apply         Create or update OpenTofu infrastructure.                                            │
│ destroy       Destroy OpenTofu-managed infrastructure.                                             │
│ output        Read an output variable from the OpenTofu state.                                     │
│ validate      Validate the OpenTofu configuration files in a directory.                            │
│ fmt           Rewrites OpenTofu configuration files to canonical format.                           │
│ status        Show OpenTofu directory state, initialization status, and provider plugins.          │
│ deploy-cloud  Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.                       │
│ lint          Run TFLint static analysis on Terraform/OpenTofu configurations.                     │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "tls": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ ca          Generate a self-signed Root Certificate Authority (CA) key pair.                       │
│ cert        Generate an X.509 TLS certificate signed by local CA or self-signed.                   │
│ homelab     Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).        │
│ inspect     Inspect and display metadata of an X.509 certificate.                                  │
│ verify      Verify an X.509 certificate cryptographic chain against a CA certificate.              │
│ enable-k8s  Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces.       │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "uv": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 uv dependency management proxies.

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ sync            Sync project dependencies into the virtual environment.                            │
│ lock            Regenerate the uv lockfile.                                                        │
│ python-install  Install project Python version with uv.                                            │
│ run             Run an arbitrary command using `uv run`.                                           │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "workspace": """

 Usage: root [OPTIONS] COMMAND [ARGS]...

 Manage multi-root VS Code workspace files (.code-workspace).

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion            Install completion for the current shell.                          │
│ --show-completion               Show completion for the current shell, to copy it or customize the │
│                                 installation.                                                      │
│ --help                -h        Show this message and exit.                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────╮
│ add       Add a folder to the VS Code workspace file.                                              │
│ remove    Remove a folder from the VS Code workspace file.                                         │
│ generate  Regenerate the workspace file from all repos in the repos directory.                     │
│ open      Open the workspace in VS Code.                                                           │
│ clean     Clean stale review sessions, old analysis caches, and temporary traces under .data/.     │
╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
}


def is_help_requested(args: list[str]) -> bool:
    """Return True if the argument list represents a help query or standalone dry-run."""
    if not args:
        return True
    if len(args) == 1 and args[0] == "--dry-run":
        return True
    return any(a in ("-h", "--help") for a in args)


def is_version_requested(args: list[str]) -> bool:
    """Return True if the argument list represents a version query."""
    return len(args) == 1 and args[0] in ("-v", "--version")


def get_help_text(args: list[str]) -> str | None:
    """Return pre-rendered help text if available for the given CLI arguments."""
    if not args or (len(args) == 1 and args[0] in ("-h", "--help", "--dry-run")):
        return _ROOT_HELP

    # Check for subcommand help (e.g. devops ai --help or devops --help ai)
    non_flags = [a for a in args if not a.startswith("-")]
    if non_flags:
        subcmd = non_flags[0]
        if subcmd in _SUBCOMMAND_HELPS and any(a in ("-h", "--help") for a in args):
            return _SUBCOMMAND_HELPS[subcmd]

    return None


def show_help(args: list[str]) -> bool:
    """Print help text to stdout and return True if handled."""
    text = get_help_text(args)
    if text is not None:
        sys.stdout.write(text + "\n")
        return True
    return False


def show_version() -> None:
    """Print version to stdout."""
    sys.stdout.write(f"devops-cli {__version__}\n")
