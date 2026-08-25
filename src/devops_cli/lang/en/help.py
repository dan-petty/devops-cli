"""Centralized CLI help strings catalog for devops-cli (English)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OptionHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class AICommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class K8sCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Manage Kubernetes clusters, pods, services, and workloads."
    pods: str = "List running pods across namespaces with health metrics."
    status: str = "Cluster health and resource utilization summary."
    port_forward: str = "Forward local port to a remote Kubernetes service."


class SSHCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Generate, rotate, audit, and register Ed25519 SSH keypairs."
    generate: str = "Generate a new Ed25519 SSH keypair with 90-day expiry naming."
    status: str = "Show currently active SSH key and days until expiration."
    audit: str = "Audit SSH key configuration and recommend rotation if near expiry."


class BranchesCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Branch management and Jira workflows."
    sync: str = "Fetch and pull tracking branches across all workspace repositories."
    jira: str = "Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."
    list_all: str = "List branches across all workspace repositories."
    clean: str = "Delete local branches that have been merged into the default branch."


class WorkspaceCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Manage multi-root VS Code workspace files (.code-workspace)."
    sync: str = "Synchronize VS Code workspace file with all cloned repositories."
    add: str = "Add a repository folder into the VS Code workspace file."
    remove: str = "Remove a repository folder from the VS Code workspace file."
    generate: str = "Regenerate workspace file from all repositories in base directory."
    open_ws: str = "Open the workspace file in VS Code."


class ReposCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Clone, synchronize, and manage organization repositories."
    clone_org: str = "Clone all repositories belonging to a GitHub organization."
    clone: str = "Clone a specific GitHub repository."
    list_repos: str = "List cloned repositories and their git status."
    sync: str = "Synchronize all cloned repositories with their remotes."


class UVCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "uv dependency management proxies."
    sync: str = "Sync project dependencies into the virtual environment."
    lock: str = "Generate or update uv.lock file."
    audit: str = "Audit installed packages and dependencies for known vulnerabilities."
    pip: str = "Proxy command for uv pip interface."
    python: str = "Manage Python runtime versions with uv."
    run: str = "Run an arbitrary command using uv run in the virtual environment."


class TfCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "OpenTofu and Terraform Infrastructure-as-Code operations."
    init: str = "Initialize OpenTofu/Terraform working directory and download providers."
    plan: str = "Generate and show an execution plan for infrastructure changes."
    apply: str = "Create or update infrastructure according to configuration."
    destroy: str = "Destroy managed infrastructure resources."
    output: str = "Read an output variable from the state file."
    validate_cmd: str = "Validate the configuration files in a directory."
    fmt: str = "Format OpenTofu/Terraform configuration files to standard format."


class KustomizeCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Kustomize build and apply operations."
    build: str = "Build kustomize overlays (delegates to kustomize build)."
    diff: str = "Show a diff of pending changes (delegates to kubectl diff -k)."
    apply: str = "Apply a kustomization (delegates to kubectl apply -k)."


class ToolDocHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    list_files: str = "List non-hidden files in the specified directory up to 2 levels deep."
    read_file: str = "Read contents of a text file up to max_bytes."
    git_status: str = "Return current git status summary."
    git_diff: str = "Return current unstaged git diff up to 4000 characters."
    search_code: str = "Search workspace source code files for a string query."
    k8s_pods: str = "Query pods in a Kubernetes namespace."
    argo_apps: str = "Query ArgoCD applications in minikube/k8s cluster."
    scan_trivy: str = "Run Aqua Trivy vulnerability, secret, misconfiguration, and IaC scanner."


class HelpCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    options: OptionHelp = OptionHelp()
    ai: AICommandHelp = AICommandHelp()
    k8s: K8sCommandHelp = K8sCommandHelp()
    ssh: SSHCommandHelp = SSHCommandHelp()
    branches: BranchesCommandHelp = BranchesCommandHelp()
    workspace: WorkspaceCommandHelp = WorkspaceCommandHelp()
    repos: ReposCommandHelp = ReposCommandHelp()
    uv: UVCommandHelp = UVCommandHelp()
    tf: TfCommandHelp = TfCommandHelp()
    kustomize: KustomizeCommandHelp = KustomizeCommandHelp()
    tools: ToolDocHelp = ToolDocHelp()


HELP = HelpCatalog()
