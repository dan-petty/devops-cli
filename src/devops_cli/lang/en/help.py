"""Centralized CLI help strings catalog for devops-cli (English)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OptionHelp:
    repo: str = "Repository root directory (default: current directory)."
    persona: str = "Reviewer persona to activate (devsecops, architect, pm, auditor, qa)."
    all_personas: str = "Run all reviewer personas in sequence."
    base_branch: str = "Base git branch to diff against (default: main)."
    format_type: str = "Output format type (table, json, yaml, markdown)."
    dry_run: str = "Preview execution plan without mutating external state."
    verbose: str = "Enable detailed logging output."
    timeout: str = "Timeout duration in seconds."
    context: str = "Kubernetes cluster context name."
    namespace: str = "Kubernetes namespace."
    output_path: str = "Destination file path for output report or artifacts."
    workspace_file: str = "Target VS Code workspace file (.code-workspace or .json)."
    base_dir: str = "Base repository root directory."
    force: str = "Force execution ignoring non-blocking warnings."
    auto_approve: str = "Skip interactive confirmation prompts."


@dataclass(frozen=True)
class AICommandHelp:
    app: str = "Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot)."
    chat: str = "Interactive multi-turn AI chat session with optional tool execution."
    config: str = "Show or update AI provider configuration (provider, model, endpoints, keys)."
    test: str = "Send a test prompt to verify AI provider connectivity."
    agents: str = "Generate or regenerate AGENTS.md, CLAUDE.md, and copilot-instructions.md."
    review: str = "AI-powered multi-persona code review system."
    analyze: str = "Analyze codebase metadata and generate structural outlines."
    rag: str = "Manage RAG vector embeddings, indexing, and semantic search (Qdrant)."
    benchmark: str = (
        "Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks."
    )
    cache: str = "Manage LLM response cache, performance metrics, and warm starting points."


@dataclass(frozen=True)
class K8sCommandHelp:
    app: str = "Manage Kubernetes clusters, pods, services, and workloads."
    pods: str = "List running pods across namespaces with health metrics."
    status: str = "Cluster health and resource utilization summary."
    port_forward: str = "Forward local port to a remote Kubernetes service."


@dataclass(frozen=True)
class SSHCommandHelp:
    app: str = "Generate, rotate, audit, and register Ed25519 SSH keypairs."
    generate: str = "Generate a new Ed25519 SSH keypair with 90-day expiry naming."
    status: str = "Show currently active SSH key and days until expiration."
    audit: str = "Audit SSH key configuration and recommend rotation if near expiry."


@dataclass(frozen=True)
class BranchesCommandHelp:
    app: str = "Branch management and Jira workflows."
    sync: str = "Fetch and pull tracking branches across all workspace repositories."
    jira: str = "Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."
    list_all: str = "List branches across all workspace repositories."
    clean: str = "Delete local branches that have been merged into the default branch."


@dataclass(frozen=True)
class WorkspaceCommandHelp:
    app: str = "Manage multi-root VS Code workspace files (.code-workspace)."
    sync: str = "Synchronize VS Code workspace file with all cloned repositories."
    add: str = "Add a repository folder into the VS Code workspace file."
    remove: str = "Remove a repository folder from the VS Code workspace file."
    generate: str = "Regenerate workspace file from all repositories in base directory."
    open_ws: str = "Open the workspace file in VS Code."


@dataclass(frozen=True)
class ReposCommandHelp:
    app: str = "Clone, synchronize, and manage organization repositories."
    clone_org: str = "Clone all repositories belonging to a GitHub organization."
    clone: str = "Clone a specific GitHub repository."
    list_repos: str = "List cloned repositories and their git status."
    sync: str = "Synchronize all cloned repositories with their remotes."


@dataclass(frozen=True)
class UVCommandHelp:
    app: str = "uv dependency management proxies."
    sync: str = "Sync project dependencies into the virtual environment."
    lock: str = "Generate or update uv.lock file."
    audit: str = "Audit installed packages and dependencies for known vulnerabilities."
    pip: str = "Proxy command for uv pip interface."
    python: str = "Manage Python runtime versions with uv."
    run: str = "Run an arbitrary command using uv run in the virtual environment."


@dataclass(frozen=True)
class TfCommandHelp:
    app: str = "OpenTofu and Terraform Infrastructure-as-Code operations."
    init: str = "Initialize OpenTofu/Terraform working directory and download providers."
    plan: str = "Generate and show an execution plan for infrastructure changes."
    apply: str = "Create or update infrastructure according to configuration."
    destroy: str = "Destroy managed infrastructure resources."
    output: str = "Read an output variable from the state file."
    validate_cmd: str = "Validate the configuration files in a directory."
    fmt: str = "Format OpenTofu/Terraform configuration files to standard format."


@dataclass(frozen=True)
class KustomizeCommandHelp:
    app: str = "Kustomize build and apply operations."
    build: str = "Build kustomize overlays (delegates to kustomize build)."
    diff: str = "Show a diff of pending changes (delegates to kubectl diff -k)."
    apply: str = "Apply a kustomization (delegates to kubectl apply -k)."


@dataclass(frozen=True)
class ToolDocHelp:
    list_files: str = "List non-hidden files in the specified directory up to 2 levels deep."
    read_file: str = "Read contents of a text file up to max_bytes."
    git_status: str = "Return current git status summary."
    git_diff: str = "Return current unstaged git diff up to 4000 characters."
    search_code: str = "Search workspace source code files for a string query."
    k8s_pods: str = "Query pods in a Kubernetes namespace."
    argo_apps: str = "Query ArgoCD applications in minikube/k8s cluster."
    scan_trivy: str = "Run Aqua Trivy vulnerability, secret, misconfiguration, and IaC scanner."


@dataclass(frozen=True)
class ArgoCommandHelp:
    app: str = "Argo CD, Workflows, and Rollouts management."
    cd: str = "ArgoCD application management."
    workflows: str = "Argo Workflows management."
    rollouts: str = "Argo Rollouts management."
    apps_list: str = "List all ArgoCD applications."
    apps_sync: str = "Trigger sync for an ArgoCD application."
    apps_get: str = "Get details of an ArgoCD application."


@dataclass(frozen=True)
class CICommandHelp:
    app: str = "Run tests, linting, formatting, and type-checks."
    remote: str = "Inspect and watch remote GitHub Actions CI workflow runs."


@dataclass(frozen=True)
class DevcontainerCommandHelp:
    app: str = "Manage devcontainer configurations."
    init: str = "Scaffold .devcontainer/ using the published DevOps CLI devcontainer image."
    update: str = "Update the Python image version in an existing devcontainer.json."
    validate: str = (
        "Validate .devcontainer/devcontainer.json manifest syntax and configuration schema."
    )
    list_cmd: str = "List repos with their devcontainer status."
    post_create: str = (
        "Execute DevContainer post-create setup tasks (history, shell completions, config prep)."
    )
    post_start: str = "Execute DevContainer post-start lifecycle tasks."


@dataclass(frozen=True)
class DockerCommandHelp:
    app: str = "Docker image management."
    images: str = "List local Docker images."
    build: str = "Build a Docker image."
    push: str = "Push a Docker image to a registry."
    prune: str = "Remove unused containers, images, and networks."
    analyze_layers: str = "Analyze container image layer efficiency and wasted space using Dive."


@dataclass(frozen=True)
class GrafanaCommandHelp:
    app: str = "Grafana dashboard and alert management."
    dashboards: str = "Manage Grafana dashboards."
    search: str = "Search Grafana dashboards and folders by query string."
    datasources: str = "List configured datasources."
    alerts: str = "List alert rules (Grafana 9+ unified alerting)."


@dataclass(frozen=True)
class MCPCommandHelp:
    app: str = "FastMCP server and Model Context Protocol integrations."
    serve: str = "Launch FastMCP server to expose devops-cli tools to MCP clients."
    tools: str = "List all registered FastMCP tools and descriptions."


@dataclass(frozen=True)
class ServeCommandHelp:
    app: str = (
        "FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics."
    )


@dataclass(frozen=True)
class DocsCommandHelp:
    app: str = "Generate and synchronize CLI documentation and markdown matrices."
    generate: str = "Generate reference documentation and sync command matrix in README.md."
    check: str = "Verify that documentation is strictly up to date with CLI code."


@dataclass(frozen=True)
class PRCommandHelp:
    app: str = "GitHub Pull Request workflows and reviews."
    list_prs: str = "List pull requests matching filters."
    create_pr: str = "Create a new pull request."
    checks: str = "View status of remote CI checks on a pull request."


@dataclass(frozen=True)
class ReleaseCommandHelp:
    app: str = "Automate version bumps, changelogs, tags, and GitHub releases."
    status: str = "Check working tree status and latest release tags."
    prepare: str = "Prepare a release version bump and synchronize changelog and docs."
    tag: str = "Create and push a git release tag."
    pr: str = "Open a release Pull Request targeting main."


@dataclass(frozen=True)
class ReviewCommandHelp:
    app: str = "AI-powered multi-persona code review and security audits."
    path_cmd: str = "Review local files or directory changes."
    branch_cmd: str = "Review diff between branches."
    pr_cmd: str = "Review a GitHub Pull Request."
    findings: str = "Manage and update review findings."
    stats: str = "Show review sessions and findings statistics."
    export_feedback: str = "Export review findings to structured feedback files."


@dataclass(frozen=True)
class ScanCommandHelp:
    app: str = "Security scanner suite: Trivy, Gitleaks, Semgrep, Checkov, Kubeconform."
    trivy: str = "Run Trivy security scan."
    gitleaks: str = "Run Gitleaks secret detection scan."
    semgrep: str = "Run Semgrep static analysis."
    checkov: str = "Run Checkov Infrastructure as Code security scan."
    kubeconform: str = "Run Kubeconform Kubernetes manifest validation."
    kubelinter: str = "Run KubeLinter security audit on Kubernetes manifests."
    pluto: str = "Run Pluto Kubernetes deprecated API check."
    popeye: str = "Run Popeye Kubernetes cluster sanitizer."
    dive: str = "Run Dive container image layer analysis."


@dataclass(frozen=True)
class TelemetryCommandHelp:
    app: str = "OpenTelemetry tracing, metrics, and Jaeger observability."
    status: str = "Show telemetry collector connectivity and service configuration."
    test_span: str = "Emit a synthetic test span to verify Jaeger tracing collector."


@dataclass(frozen=True)
class TLSCommandHelp:
    app: str = "Generate and manage homelab TLS certificates and CAs."
    generate_ca: str = "Generate a self-signed Root CA certificate."
    generate_cert: str = "Generate a TLS leaf certificate signed by a CA."
    inspect: str = "Inspect TLS certificate metadata and expiration."
    verify: str = "Verify certificate chain against CA."
    bundle: str = "Generate full homelab TLS certificate bundle."
    k8s_secret: str = "Create Kubernetes TLS secret in cluster namespaces."


@dataclass(frozen=True)
class ConfigCommandHelp:
    app: str = "Show, set, get, or initialize CLI configuration."
    show: str = "Display current configuration settings."
    get: str = "Get a specific configuration value."
    set_cmd: str = "Set a configuration value (stored in config file or OS Keyring)."
    init_cmd: str = "Interactive configuration wizard."


@dataclass(frozen=True)
class InstallCommandHelp:
    app: str = "Install and manage DevOps tool binaries."
    all_cmd: str = "Install all required DevOps CLI binaries."
    status: str = "Check installed DevOps toolchain versions."


@dataclass(frozen=True)
class BenchmarkCommandHelp:
    app: str = "Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks."


@dataclass(frozen=True)
class AnalyzeCommandHelp:
    app: str = (
        "Analyze codebases and create/update structured metadata files under .data/analysis/."
    )


@dataclass(frozen=True)
class PrometheusCommandHelp:
    app: str = "Prometheus metrics querying and analysis."
    query: str = "Execute an instant PromQL query."
    query_range: str = "Execute a range PromQL query."


@dataclass(frozen=True)
class RAGCommandHelp:
    app: str = "Manage RAG vector embeddings, indexing, and semantic search (Qdrant)."
    index: str = "Index codebase files into Qdrant vector database."
    index_kb: str = "Index DevOps CLI Knowledge Base into Qdrant."
    search: str = "Search indexed codebase using semantic similarity."
    collections: str = "List Qdrant vector collections and metrics."
    clear: str = "Clear a Qdrant vector collection."
    reset_cache: str = "Reset local RAG indexing cache."


@dataclass(frozen=True)
class HelpCatalog:
    options: OptionHelp = field(default_factory=OptionHelp)
    ai: AICommandHelp = field(default_factory=AICommandHelp)
    k8s: K8sCommandHelp = field(default_factory=K8sCommandHelp)
    ssh: SSHCommandHelp = field(default_factory=SSHCommandHelp)
    branches: BranchesCommandHelp = field(default_factory=BranchesCommandHelp)
    workspace: WorkspaceCommandHelp = field(default_factory=WorkspaceCommandHelp)
    repos: ReposCommandHelp = field(default_factory=ReposCommandHelp)
    uv: UVCommandHelp = field(default_factory=UVCommandHelp)
    tf: TfCommandHelp = field(default_factory=TfCommandHelp)
    kustomize: KustomizeCommandHelp = field(default_factory=KustomizeCommandHelp)
    tools: ToolDocHelp = field(default_factory=ToolDocHelp)
    argo: ArgoCommandHelp = field(default_factory=ArgoCommandHelp)
    ci: CICommandHelp = field(default_factory=CICommandHelp)
    devcontainer: DevcontainerCommandHelp = field(default_factory=DevcontainerCommandHelp)
    docker: DockerCommandHelp = field(default_factory=DockerCommandHelp)
    grafana: GrafanaCommandHelp = field(default_factory=GrafanaCommandHelp)
    mcp: MCPCommandHelp = field(default_factory=MCPCommandHelp)
    serve: ServeCommandHelp = field(default_factory=ServeCommandHelp)
    docs: DocsCommandHelp = field(default_factory=DocsCommandHelp)
    pr: PRCommandHelp = field(default_factory=PRCommandHelp)
    release: ReleaseCommandHelp = field(default_factory=ReleaseCommandHelp)
    review: ReviewCommandHelp = field(default_factory=ReviewCommandHelp)
    scan: ScanCommandHelp = field(default_factory=ScanCommandHelp)
    telemetry: TelemetryCommandHelp = field(default_factory=TelemetryCommandHelp)
    tls: TLSCommandHelp = field(default_factory=TLSCommandHelp)
    config: ConfigCommandHelp = field(default_factory=ConfigCommandHelp)
    install: InstallCommandHelp = field(default_factory=InstallCommandHelp)
    benchmark: BenchmarkCommandHelp = field(default_factory=BenchmarkCommandHelp)
    analyze: AnalyzeCommandHelp = field(default_factory=AnalyzeCommandHelp)
    prometheus: PrometheusCommandHelp = field(default_factory=PrometheusCommandHelp)
    rag: RAGCommandHelp = field(default_factory=RAGCommandHelp)


HELP = HelpCatalog()
