"""Centralized CLI help strings catalog for devops-cli (English)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MainHelp:
    app: str = "DevOps CLI — manage repos, SSH keys, Kubernetes, and more."
    version: str = "Show version and exit."
    dry_run: str = (
        "Show debug output of commands and AI requests without executing delegated "
        "subcommands or external write actions."
    )


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
    json_output: str = "Output findings or metrics as JSON."
    raw: str = "Output raw string without formatting or shell escapes."
    explain: str = "Explain command concepts, terminology, and workflows."
    pattern: str = "Glob pattern for matching files."
    provider: str = "AI or cloud provider."
    model: str = "AI model identifier."
    interactive: str = "Run in interactive mode with prompts."
    strict: str = "Enforce strict schema or syntax validation."
    limit: str = "Maximum number of items to return or display."
    state: str = "Filter by state or status."
    title: str = "Title for the item or entity."
    body: str = "Body or description text."
    draft: str = "Create pull request or entity as draft."
    labels: str = "Comma-separated labels to attach."
    push: str = "Push commits or tags to git remote."
    root: str = "Project repository root directory."
    version: str = "Target version string."
    frontier: str = "Force routing to frontier tier models."
    container: str = "Specific container name within the pod."
    follow: str = "Follow stream or log output in real time."
    k8s_context: str = "Kubernetes cluster context name."
    language: str = "Filter or target specific programming language."
    output: str = "Destination path for output report or artifacts."
    output_dir: str = "Directory path for generated output files."
    overwrite: str = "Overwrite existing files or resources if they exist."
    tail: str = "Number of recent lines to display."
    target_dir: str = "Target directory path for operation."
    workspace_dir: str = "Workspace root directory path."


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
    pipeline: str = "Run multi-agent AI pipeline execution across personas."
    bundle: str = "Bundle local AI model artifacts and instruction context."
    tokens: str = "Calculate token counts and context budget consumption."
    cost: str = "Estimate LLM inference cost for token quantities."
    ollama_urls: str = "Ollama server base URLs (comma-separated)."
    max_parallel: str = "Maximum number of simultaneous requests allowed per Ollama server node."
    api_base_url: str = "Override API base URL for any provider."
    api_key: str = "API key — stored in OS keyring, not config file."
    max_retries: str = "Maximum retry count for AI requests upon failure."
    prompt: str = "Test prompt to send to the provider."
    url: str = "Specific Ollama server URL to test."
    template: str = "Generate from built-in template without calling the LLM."
    generate_file: str = "Files to generate (repeatable)."
    context_file: str = "Optional file to inject as background context (e.g. AGENTS.md)."
    rag_context: str = "Retrieve relevant semantic RAG context."
    stream: str = "Stream response tokens."
    tools: str = "Enable DevOps agent tools."
    thinking: str = "Enable model reasoning/thinking."
    prewarm: str = "Prewarm the model before starting chat."
    explain_chat: str = "Explain chat personas, tools, and reasoning modes."
    explain_all: str = "Explain AI agent workflows, FastMCP tools, RAG terminology, and metrics."
    goal: str = "Initial goal or prompt for the multi-agent pipeline."
    personas_seq: str = "Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa)."
    max_turns: str = "Maximum tool turns per agent stage."
    token_target: str = "File path or text string to calculate tokens for."
    budget: str = "Max context token budget limit."
    cost_task: str = "Task name (e.g. review, scan)."
    est_tokens: str = "Estimated tokens."
    route: str = "Evaluate task complexity and determine the optimal LLM provider and model route."
    verify_spec: str = "Verify codebase implementation against architecture contract."
    spec_path: str = "Path to markdown architecture specification contract."
    target_dir: str = "Target source directory to verify or analyze."
    repomap: str = "Generate structural symbol and reference map for codebase."
    max_files: str = "Maximum source files to include."
    include_tests: str = "Include test modules in symbol map."
    diagram: str = "Generate Mermaid architecture topology or STRIDE threat model diagram."
    diagram_type: str = "Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model."
    eval_review: str = "Evaluate and benchmark code review quality against feedback dataset."
    dataset_path: str = "Path to feedback dataset jsonl."
    test_gen: str = "Synthesize unit test suites for functions and modules via LLM."
    test_function: str = "Specific function to synthesize tests for."
    target_file: str = "Target source file to synthesize unit tests for."


@dataclass(frozen=True)
class AICacheCommandHelp:
    app: str = "Manage LLM response cache, performance metrics, and warm starting points."
    stats: str = "Show cache hit rates, size, and efficiency metrics."
    clear: str = "Clear the LLM response cache."
    prune: str = "Prune expired LLM response cache entries."


@dataclass(frozen=True)
class K8sCommandHelp:
    app: str = "Manage Kubernetes clusters, pods, services, and workloads."
    pods: str = "List running pods across namespaces with health metrics."
    label_selector: str = "Kubernetes label selector filter (e.g. app=frontend)."
    all_namespaces: str = "Query pods across all namespaces."
    watch: str = "Continuously refresh pod list in real-time terminal display."
    interval: str = "Auto-refresh polling interval in seconds."
    status: str = "Cluster health and resource utilization summary."
    port_forward: str = "Forward local port to a remote Kubernetes service."
    switch_context: str = "Switch active kubectl context."
    apply_manifest: str = "Apply Kubernetes manifest file or directory."
    logs: str = "Fetch container logs for a pod."
    bootstrap: str = "Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress."
    deploy_stack: str = "Deploy application stacks (infra, llm, all) via Helm/Kustomize."
    teardown_stack: str = "Teardown deployed application stacks."
    urls: str = "Display ingress and service URLs for deployed stacks."
    lint: str = "Run KubeLinter static analysis on Kubernetes manifests."
    popeye: str = "Run Popeye cluster health audit and sanitizer."
    pluto: str = "Run Pluto deprecated Kubernetes API detection."
    create_tls_secret: str = "Create Kubernetes TLS secret in cluster namespaces."
    enable_tls: str = "Deploy generated TLS certificates to all Kubernetes namespaces."
    validate_manifest: str = (
        "Validate Kubernetes manifests against OpenAPI schemas with Kubeconform."
    )
    context_target: str = "Target context name to switch to."
    manifest_path: str = "Manifest file or directory path."
    pod_name: str = "Pod name."
    manifests_dir: str = "Directory containing Kubernetes manifests."
    auto_start: str = "Auto-start minikube if stopped."
    stack: str = "Stack to operate on: infra | llm | all."
    k8s_dir: str = "Path to k8s/ config directory."
    email: str = "Admin email address."
    admin_name: str = "Admin display name."
    password: str = "Admin password."
    secret_name: str = "Name of the Kubernetes TLS secret to create or update."
    cert_path: str = "Path to TLS certificate file (.crt or .pem)."
    key_path: str = "Path to TLS private key file (.key or .pem)."
    argocd_port: str = "Local port for ArgoCD."
    grafana_port: str = "Local port for Grafana."
    prometheus_port: str = "Local port for Prometheus."
    jaeger_port: str = "Local port for Jaeger Query UI."
    otel_port: str = "Local port for OpenTelemetry OTLP Traces (HTTP)."
    ollama_port: str = "Local port for Ollama."
    open_webui_port: str = "Local port for Open-WebUI."
    qdrant_port: str = "Local port for Qdrant HTTP."
    valkey_port: str = "Local port for Valkey."
    bind_address: str = "Local address to bind for port-forwarding."
    lint_target: str = "Target K8s manifest file or directory to lint."
    pluto_target: str = "Target manifest file or directory to scan for deprecated APIs."
    k8s_version: str = "Target Kubernetes OpenAPI version."
    strict_schema: str = "Disallow additional undeclared properties."
    policy_path: str = "Path to Kyverno policy or OPA rule file."
    policy_engine: str = "Policy evaluation engine (kyverno, opa)."
    pod_query: str = "Regex pattern or query to match pod names."
    tail_lines: str = "Number of historical log lines to stream."
    follow_logs: str = "Continuously stream live log output."
    helm_release: str = "Name of deployed Helm release."
    helm_chart: str = "Path to local Helm chart directory or packaged archive."
    helm_values: str = "Values YAML files to override release defaults."
    chaos_experiment: str = "Resilience experiment name (e.g., pod-kill, latency-inject)."
    chaos_deployment: str = "Target deployment to disrupt."
    chaos_duration: str = "Reconciliation monitoring window in seconds."


@dataclass(frozen=True)
class SSHCommandHelp:
    app: str = "Generate, rotate, audit, and register Ed25519 SSH keypairs."
    generate: str = "Generate a new Ed25519 SSH keypair with 90-day expiry naming."
    status: str = "Show currently active SSH key and days until expiration."
    audit: str = "Audit SSH key configuration and recommend rotation if near expiry."
    key_file: str = "Path to private key."
    key_dir: str = "Directory where SSH keys are stored."
    comment: str = "Comment to include in public key."
    force_rotate: str = "Rotate even if not yet due."


@dataclass(frozen=True)
class BranchesCommandHelp:
    app: str = "Branch management and Jira workflows."
    sync: str = "Fetch and pull tracking branches across all workspace repositories."
    jira: str = "Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."
    list_all: str = "List branches across all workspace repositories."
    clean: str = "Delete local branches that have been merged into the default branch."
    ticket_id: str = "Jira ticket ID, e.g. PROJ-123."
    slug: str = "Short branch description."
    all_branches: str = "Include remote branches."


@dataclass(frozen=True)
class WorkspaceCommandHelp:
    app: str = "Manage multi-root VS Code workspace files (.code-workspace)."
    sync: str = "Synchronize VS Code workspace file with all cloned repositories."
    add: str = "Add a repository folder into the VS Code workspace file."
    remove: str = "Remove a repository folder from the VS Code workspace file."
    generate: str = "Regenerate workspace file from all repositories in base directory."
    open_ws: str = "Open the workspace file in VS Code."
    clean: str = (
        "Clean stale review sessions, old analysis caches, and temporary traces under .data/."
    )
    older_than: str = "Prune artifacts older than N days."


@dataclass(frozen=True)
class ReposCommandHelp:
    app: str = "Clone, synchronize, and manage organization repositories."
    clone_org: str = "Clone all repositories belonging to a GitHub organization."
    clone: str = "Clone a specific GitHub repository."
    list_repos: str = "List cloned repositories and their git status."
    sync: str = "Synchronize all cloned repositories with their remotes."
    org_name: str = "GitHub organisation name."
    repo_url: str = "Repository URL (SSH or HTTPS)."


@dataclass(frozen=True)
class UVCommandHelp:
    app: str = "uv dependency management proxies."
    sync: str = "Sync project dependencies into the virtual environment."
    lock: str = "Generate or update uv.lock file."
    audit: str = "Audit installed packages and dependencies for known vulnerabilities."
    pip: str = "Proxy command for uv pip interface."
    python: str = "Manage Python runtime versions with uv."
    run: str = "Run an arbitrary command using uv run in the virtual environment."
    frozen: str = "Do not update lockfile."
    upgrade: str = "Upgrade dependencies while locking."
    version: str = "Python version to install (defaults to .python-version)."


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
    tflint: str = "Run TFLint static analysis on Terraform configuration."
    bootstrap: str = "Bootstrap cloud infrastructure with opinionated modules."
    target_dir: str = "Target directory containing OpenTofu configuration."
    var_file: str = "Path to variable definitions file."
    out_plan: str = "Write generated plan to file."
    plan_file: str = "Explicit plan file to apply."
    plan_input_file: str = "Path to raw plan output or log file."
    pr: str = "Pull Request number to post plan comment to."
    notify_plan: str = (
        "Format Terraform/OpenTofu plan output and post it as a comment on a GitHub PR."
    )
    upgrade_modules: str = "Upgrade modules and plugins."
    reconfigure: str = "Reconfigure backend, ignoring existing state."
    destroy_plan: str = "Generate a plan to destroy all resources."
    check_fmt: str = "Check formatting without writing files."
    recursive_fmt: str = "Format subdirectories recursively."
    no_color: str = "Disable color codes."
    tflint_config: str = "Path to .tflint.hcl config file."
    tflint_dry_run: str = "Simulate TFLint execution."


@dataclass(frozen=True)
class KustomizeCommandHelp:
    app: str = "Kustomize build and apply operations."
    build: str = "Build kustomize overlays (delegates to kustomize build)."
    diff: str = "Show a diff of pending changes (delegates to kubectl diff -k)."
    apply: str = "Apply a kustomization (delegates to kubectl apply -k)."
    path: str = "Path to kustomization directory."
    output_target: str = "Output file or directory."
    output: str = "Destination file or directory for generated manifests."
    target_dir: str = "Target kustomize directory path."


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
    app_of_apps: str = "Deploy complete homelab stack via root App-of-Apps pattern."
    app_of_apps_manifest: str = "Path to root ArgoCD App-of-Apps manifest."
    app_name: str = "Application name."
    workflow_file: str = "Workflow YAML file."
    workflow_name: str = "Workflow name."
    rollout_name: str = "Rollout name."
    follow: str = "Stream workflow execution logs."
    prune: str = "Allow deletion of resources omitted from the source repository."
    wait: str = "Wait for sync operation to finish."
    watch: str = "Watch application status changes live."
    interval: str = "Auto-refresh polling interval in seconds."


@dataclass(frozen=True)
class CICommandHelp:
    app: str = "Run tests, linting, formatting, and type-checks."
    remote: str = "Inspect and watch remote GitHub Actions CI workflow runs."
    test_cmd: str = "Run unit and integration test suite via pytest."
    coverage: str = "Run test suite and calculate code coverage percentage."
    lint: str = "Run static analysis checks (ruff, actionlint, security audit)."
    format_cmd: str = "Check or apply automated code formatting (ruff format)."
    typecheck: str = "Run strict static type analysis (mypy)."
    audit: str = "Audit installed dependencies for known vulnerabilities."
    filter_keyword: str = "Filter tests by keyword expression."
    stop_fail: str = "Stop after first failure."
    num_workers: str = "Number of parallel worker processes."
    html_report: str = "Generate HTML coverage report in .data/htmlcov/."
    xml_report: str = "Generate XML coverage report in .data/coverage.xml."
    auto_fix: str = "Auto-fix violations where possible."
    format_fix: str = "Apply formatting changes in-place."
    min_severity: str = "Minimum severity threshold (low, medium, high)."
    fix_all: str = "Auto-fix lint/format before reporting status."
    fix_sync: str = "Automatically synchronize dependencies and lockfile."
    maintain: str = (
        "Run automated toolchain, dependency freshness, and lockfile maintenance checks."
    )


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
    setup: str = "Execute DevContainer lifecycle tasks (post-create, post-start, or all)."
    repo_path: str = "Path to the repository."
    project_name: str = "Project name."
    python_version: str = "Python version for base template."
    image: str = "Base container image (defaults to published devops-cli image)."
    published: str = "Use published GHCR image (defaults to True)."
    volume_name: str = "Custom volume name for /home/vscode (defaults to <project_name>-home)."
    overwrite: str = "Overwrite existing devcontainer.json and configurations."
    workspace_dir: str = "Path to workspace directory containing .devcontainer."
    config_file: str = "Direct path to devcontainer.json."
    validate_dry_run: str = "Simulate DevContainer manifest validation."
    run_post_create: str = "Execute post-create setup tasks."
    run_post_start: str = "Execute post-start lifecycle tasks."
    run_all: str = "Execute all DevContainer lifecycle tasks."
    bootstrap_k8s: str = (
        "Execute Minikube startup and Kubernetes stack deployment in the background."
    )
    auto_deploy: str = "Auto-deploy Kubernetes stack after cluster startup."
    stack: str = "Kubernetes stack to deploy (e.g. infra, llm, monitoring, all)."


@dataclass(frozen=True)
class DockerCommandHelp:
    app: str = "Docker image management."
    images: str = "List local Docker images."
    build: str = "Build a Docker image."
    push: str = "Push a Docker image to a registry."
    prune: str = "Remove unused containers, images, and networks."
    stats: str = "Display live container CPU, memory, and network I/O statistics."
    analyze_layers: str = "Analyze container image layer efficiency and wasted space using Dive."
    filter_name: str = "Filter by name."
    context_dir: str = "Build context directory."
    image_tag: str = "Image name[:tag] to push."
    remove_volumes: str = "Also remove unused volumes."
    skip_confirm: str = "Skip confirmation."
    image_analyze: str = "Container image tag or ID to analyze."
    dockerfile: str = "Path to Dockerfile."
    image_name: str = "Docker image name or repository tag."
    name_filter: str = "Filter containers or images by name."
    no_cache: str = "Do not use cached image layers when building."
    tag: str = "Image tag name."
    volumes: str = "Include or prune volumes."
    watch: str = "Continuously refresh output in the terminal at a fixed interval."
    interval: str = "Auto-refresh polling interval in seconds."


@dataclass(frozen=True)
class GrafanaCommandHelp:
    app: str = "Grafana dashboard and alert management."
    dashboards: str = "Manage Grafana dashboards."
    search: str = "Search Grafana dashboards and folders by query string."
    datasources: str = "List configured datasources."
    alerts: str = "List alert rules (Grafana 9+ unified alerting)."
    uid: str = "Dashboard UID."
    file: str = "Dashboard JSON file."
    dir: str = "Directory containing dashboard JSON files."
    query: str = "Search query."
    dashboards_dir: str = "Directory path containing dashboard definitions."
    folder_id: str = "Target Grafana folder ID for dashboard import."
    import_file: str = "Path to dashboard JSON file to import."


@dataclass(frozen=True)
class MCPCommandHelp:
    app: str = "FastMCP server and Model Context Protocol integrations."
    serve: str = "Launch FastMCP server to expose devops-cli tools to MCP clients."
    tools: str = "List all registered FastMCP tools and descriptions."
    transport: str = "Transport protocol for FastMCP server (stdio | sse)."
    host: str = "Host interface for SSE transport."
    port: str = "Port number for SSE transport."
    allow_remote: str = "Permit binding SSE transport to non-loopback network interfaces."


@dataclass(frozen=True)
class ServeCommandHelp:
    app: str = (
        "FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics."
    )
    host: str = "Network interface host to bind the HTTP server."
    port: str = "TCP port to listen on."
    reload: str = "Enable auto-reload on code changes (development mode)."
    workers: str = "Number of worker processes."
    log_level: str = "Logging level (debug, info, warning, error)."
    docs: str = "Enable or disable Swagger UI (/docs) and ReDoc (/redoc)."


@dataclass(frozen=True)
class DocsCommandHelp:
    app: str = "Generate and validate CLI and architecture documentation."
    generate: str = "Generate reference documentation and sync command matrix in README.md."
    check: str = "Verify that documentation is strictly up to date with CLI code."
    check_readme: str = "Verify README.md table is synchronized without writing changes."
    target_dir: str = "Target directory for generated documentation files (default: docs/)."
    output_dir: str = "Target directory for generated documentation files (default: docs/)."
    format_type: str = "Documentation output format ('markdown' or 'json')."
    sync_readme: str = "Synchronize Complete Command Matrix in README.md."
    readme_path: str = "Path to README.md file (default: workspace root README.md)."
    validate_only: str = "Validate that existing documentation is up to date without writing files."
    check_sync: str = "Verify README.md Command Matrix synchronization as well."


@dataclass(frozen=True)
class PRCommandHelp:
    app: str = "GitHub Pull Request workflows and reviews."
    list_prs: str = "List pull requests matching filters."
    create_pr: str = "Create a new pull request."
    checks: str = "View status of remote CI checks on a pull request."
    view: str = "View details of a pull request."
    diff: str = "View diff of a pull request."
    edit: str = "Edit title, body, or base branch of a pull request."
    number: str = "Pull request number."
    target_repo: str = "Target repository in OWNER/REPO format."
    state_filter: str = "Filter by state (open, closed, merged, all)."
    edit_base: str = "Change the base branch for this pull request."
    edit_title: str = "Set the new title."
    edit_body: str = "Set the new body."


@dataclass(frozen=True)
class ReleaseCommandHelp:
    app: str = "Automate version bumps, changelogs, tags, and GitHub releases."
    status: str = "Check working tree status and latest release tags."
    prepare: str = "Prepare a release version bump and synchronize changelog and docs."
    tag: str = "Create and push a git release tag."
    pr: str = "Open a release Pull Request targeting main."
    notes: str = "Extract release notes from CHANGELOG.md for a version."
    target_version: str = "Target semantic version (e.g., 0.1.8)."
    sync_docs: str = "Regenerate CLI reference docs and sync README matrix."
    ensure_changelog: str = "Ensure CHANGELOG.md contains release header with current date."
    auto_pr: str = "Create release branch, commit changes, and open a GitHub Release PR."
    prefix: str = "Conventional commit prefix (feat or fix)."
    breaking: str = "Flag release as containing breaking changes (!)."
    skip_ci: str = "Skip running the 7-gate CI test suite."
    allow_dirty: str = "Allow uncommitted changes in git repository."
    tag_message: str = "Custom tag annotation message."


@dataclass(frozen=True)
class ReviewCommandHelp:
    app: str = "AI-powered multi-persona code review and security audits."
    path_cmd: str = "Review local files or directory changes."
    branch_cmd: str = "Review diff between branches."
    pr_cmd: str = "Review a GitHub Pull Request."
    findings: str = "Manage and update review findings."
    stats: str = "Show review sessions and findings statistics."
    export_feedback: str = "Export review findings to structured feedback files."
    patch_cmd: str = "Inspect or apply suggested remediation patches from review findings."
    target_path: str = "File(s) or directory(ies) to review."
    target_branch: str = "Branch to review (default: current branch)."
    pr_number: str = "Pull request number."
    post_pr: str = "Post the review as a comment on the GitHub PR."
    summary: str = "Show segment metadata without running a full review."
    session: str = "Session ID or substring (default: latest)."
    status_filter: str = "Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED."
    unverified: str = "Show unverified findings only."
    invalidated: str = "Show invalidated findings only."
    verified: str = "Show verified findings only."
    finding_index: str = "1-based finding index in session to verify."
    title_match: str = "Match finding by substring in title."
    status_target: str = "Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED."
    reason: str = "Explanation or justification for the status change."
    reviews_dir: str = "Directory containing review sessions."
    output_feedback: str = "Output JSONL path for benchmark feedback dataset."
    status_export: str = "Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL."
    interactive_patch: str = "Preview patch diff interactively."
    explain_review: str = "Explain code review personas, severity levels, and terminology."
    no_pre_analysis: str = "Disable pre-analysis and metadata refresh."
    pre_analysis_only: str = "Run pre-analysis only and skip subsequent stages."
    no_static_scan: str = "Disable static security scanning."
    static_scan_only: str = "Run static scanning only and skip subsequent stages."
    no_persona_review: str = "Disable multi-persona LLM inspection."
    persona_review_only: str = "Run persona review only and skip subsequent stages."
    no_verification: str = "Disable finding verification and adversarial debate."
    verification_only: str = "Run verification only and skip subsequent stages."
    no_reranking: str = "Disable finding re-ranking and deduplication."
    reranking_only: str = "Run re-ranking only and skip subsequent stages."
    no_reporting: str = "Disable consolidated report generation."
    reporting_only: str = "Run report generation only."
    append_cache: str = "Append cached response to the LLM prompt as context instead of using it directly as the final response."
    no_cache: str = "Bypass LLM response cache and force fresh inference."
    force_review: str = "Force fresh review execution without cache."
    details: str = "Display full finding descriptions and fix recommendations."
    remediate: str = "Create a git remediation branch for an identified review finding."
    remediate_finding_id: str = "Finding ID or title to create remediation branch for."
    remediate_file: str = "Target source file to apply fix to."
    remediate_branch: str = "Custom topic branch name."


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
    target: str = "Target directory, file, or repository to scan."
    target_secrets: str = "Target directory or file to scan for secrets."
    target_semgrep: str = "Target directory or file to scan with Semgrep AST rules."
    target_checkov: str = "Target directory or file to scan with Checkov IaC rules."
    scan_type: str = "Trivy scan mode: fs, image, iac, repo."
    severity: str = "Comma-separated severity levels to include."
    semgrep_config: str = "Semgrep ruleset config (e.g. p/default, p/security-audit)."
    complexity: str = "Run AST-based cyclomatic complexity and indentation depth analysis."
    sbom: str = "Generate Software Bill of Materials (SBOM) in CycloneDX, SPDX, or JSON format."
    target_complexity: str = "Target directory or Python file to analyze for complexity."
    max_complexity: str = "Maximum acceptable cyclomatic complexity per function (default 10)."
    max_indent: str = "Maximum acceptable indentation / nesting depth (default 5)."
    sbom_format: str = "SBOM format output (cyclonedx, spdx, json)."
    sbom_output: str = "Destination file path for generated SBOM document."
    framework: str = "Specific IaC framework (e.g. terraform)."


@dataclass(frozen=True)
class TelemetryCommandHelp:
    app: str = "OpenTelemetry tracing, metrics, and Jaeger observability."
    status: str = "Show telemetry collector connectivity and service configuration."
    test_span: str = "Emit a synthetic test span to verify Jaeger tracing collector."
    span_name: str = "Name for test span."
    profile: str = (
        "Display terminal-rendered waterfall breakdown and latency heatmap of OpenTelemetry spans."
    )
    command_to_profile: str = (
        "CLI command string to profile and render waterfall for (e.g. 'devops k8s contexts')."
    )
    trace_id: str = "Specific trace ID to visualize from in-memory span buffer."
    last: str = "Render waterfall for the most recently executed command trace."


@dataclass(frozen=True)
class TLSCommandHelp:
    app: str = "Generate and manage homelab TLS certificates and CAs."
    generate_ca: str = "Generate a self-signed Root CA certificate."
    generate_cert: str = "Generate a TLS leaf certificate signed by a CA."
    inspect: str = "Inspect TLS certificate metadata and expiration."
    verify: str = "Verify certificate chain against CA."
    bundle: str = "Generate full homelab TLS certificate bundle."
    k8s_secret: str = "Create Kubernetes TLS secret in cluster namespaces."
    output_dir: str = "Directory to save certificate and key files."
    common_name: str = "Common Name for the certificate (e.g. *.local.lan)."
    organization: str = "Organization name."
    country: str = "2-letter country code."
    validity_days: str = "Validity period in days."
    key_size: str = "RSA key size in bits (2048 or 4096)."
    overwrite: str = "Overwrite existing files."
    san: str = "Subject Alternative Names (DNS names or IP addresses)."
    ca_cert: str = "Path to signing CA certificate (ca.crt)."
    ca_key: str = "Path to signing CA private key (ca.key)."
    domain: str = "Additional custom domains to include in SANs."
    ip: str = "Additional custom IP addresses to include in SANs."
    cert_file: str = "Path to X.509 certificate file (.crt or .pem)."
    leaf_cert: str = "Path to leaf certificate file (.crt or .pem)."
    tls_dir: str = "Directory with generated TLS certificates."
    target_dir: str = "Directory with generated TLS certificates."
    secret_name: str = "Kubernetes TLS secret name to create."


@dataclass(frozen=True)
class ConfigCommandHelp:
    app: str = "Show, set, get, or initialize CLI configuration."
    show: str = "Display current configuration settings."
    get: str = "Get a specific configuration value."
    set_cmd: str = "Set a configuration value (stored in config file or OS Keyring)."
    init_cmd: str = "Interactive configuration wizard."
    audit_keys: str = (
        "Audit OS Keyring token health, backend status, and zero-plaintext secret compliance."
    )
    key: str = "Dotted config key, e.g. github.default_org."
    value: str = "Value to set."
    export_env: str = "Print environment variables as shell export statements."
    json_env: str = "Print environment variables as JSON."
    secret_key: str = "Dotted secret key, e.g. github.token."
    secret_token: str = "Secret token string."
    destination: str = "Destination Syslog or HTTP URL."


@dataclass(frozen=True)
class InstallCommandHelp:
    app: str = "Install and manage DevOps tool binaries."
    all_cmd: str = "Install all required DevOps CLI binaries."
    status: str = "Check installed DevOps toolchain versions."
    tool: str = "Install a specific tool."
    version: str = "Specific version, e.g. v1.30.0."


@dataclass(frozen=True)
class BenchmarkCommandHelp:
    app: str = "Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks."
    models: str = (
        "Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434')."
    )
    ollama_urls: str = (
        "Comma-separated Ollama server URLs for concurrent execution "
        "(e.g. 'http://node1:11434,http://node2:11434')."
    )
    tasks: str = "Filter specific task categories or IDs (e.g. 'security,kubernetes')."
    workers: str = "Number of concurrent model server workers (default: automatic per model count)."
    test_doc: str = "Path to large test document for in-memory tokenization and section retrieval."
    samples: str = "Number of random sections to sample for retrieval evaluation."
    mode: str = "Benchmark mode: 'auto', 'chat', 'embedding'."
    explain: str = "Explain benchmark metrics, terminology, and mathematical formulas."


@dataclass(frozen=True)
class AnalyzeCommandHelp:
    app: str = (
        "Analyze codebases and create/update structured metadata files under .data/analysis/."
    )
    path_cmd: str = "Analyze file or directory codebase structure."
    branch_cmd: str = "Analyze modified files between git branches."
    pr_cmd: str = "Analyze modified files in a GitHub Pull Request."
    target: str = "File or directory path to analyze."
    target_branch: str = "Branch to analyze (default: active branch)."
    pr_number: str = "GitHub PR number to analyze."
    enhanced: str = "Generate AI-enhanced metadata (pseudocode, complexity, last_updated)."
    force: str = "Regenerate all enhanced metadata fields regardless of last_* timestamps."
    explain: str = "Explain static code analysis metrics and terminology."


@dataclass(frozen=True)
class PrometheusCommandHelp:
    app: str = "Prometheus metrics querying and analysis."
    query: str = "Execute an instant PromQL query."
    query_range: str = "Execute a range PromQL query."
    expr: str = "PromQL expression."
    eval_time: str = "Evaluation time (RFC3339 or Unix)."
    start_time: str = "Start: duration ago (e.g. 1h) or Unix ts."
    end_time: str = "Query range end timestamp or relative duration."
    step: str = "Query resolution step interval."
    time_at: str = "Evaluation timestamp for instant vector query."


@dataclass(frozen=True)
class RAGCommandHelp:
    app: str = "Manage RAG vector embeddings, indexing, and semantic search (Qdrant)."
    index: str = "Index codebase files into Qdrant vector database."
    index_kb: str = "Index DevOps CLI Knowledge Base into Qdrant."
    search: str = "Search indexed codebase using semantic similarity."
    collections: str = "List Qdrant vector collections and metrics."
    clear: str = "Clear a Qdrant vector collection."
    reset_cache: str = "Reset local RAG indexing cache."
    target: str = "Directory or file to index into vector store."
    project: str = "Project / repository name override."
    include_kb: str = "Include bundled DevOps CLI Knowledge Base in docs collection."
    collection: str = "Target collection override."
    query: str = "Natural language query or code search term."
    category: str = "Filter by category (code, docs, topics, tasks)."
    top_k: str = "Number of results to return."
    min_score: str = "Minimum similarity score (0.0 - 1.0)."
    file_filter: str = "Filter by filepath glob pattern."
    reset: str = "Alias for clear — clear vector index collections and reset local cache."
    explain: str = "Explain RAG vector embeddings, Qdrant indexing, and terminology."


@dataclass(frozen=True)
class TestCommandHelp:
    app: str = "Test suite orchestration, git-diff aware test selector, and load testing."
    run: str = "Execute pytest test suite with optional git-diff aware test selection."
    load: str = "Execute developer-centric load and latency tests against services using k6."
    script_path: str = "Path to k6 JavaScript test script or endpoint definition."
    vus: str = "Number of concurrent virtual users (VUs)."
    duration: str = "Test execution duration (e.g. 30s, 1m)."
    summary_export: str = "Path to export JSON summary metrics."
    changed: str = "Run only tests related to files modified in git working tree or current branch."
    coverage: str = "Run with code coverage analysis."
    fail_fast: str = "Stop immediately on the first test failure."
    verbose: str = "Enable verbose pytest output (-vv)."
    dry_run: str = "Simulate test execution."


@dataclass(frozen=True)
class PipelineCommandHelp:
    app: str = "Programmable containerized pipeline execution (Dagger)."
    run: str = "Execute reproducible, containerized developer pipelines with Dagger."
    pipeline_path: str = "Path to Dagger module directory or pipeline script."
    function_name: str = "Target pipeline function to call."
    args: str = "Arguments to forward to the pipeline execution."


@dataclass(frozen=True)
class HelpCatalog:
    main: MainHelp = field(default_factory=MainHelp)
    options: OptionHelp = field(default_factory=OptionHelp)
    ai: AICommandHelp = field(default_factory=AICommandHelp)
    ai_cache: AICacheCommandHelp = field(default_factory=AICacheCommandHelp)
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
    test: TestCommandHelp = field(default_factory=TestCommandHelp)
    pipeline: PipelineCommandHelp = field(default_factory=PipelineCommandHelp)


HELP = HelpCatalog()
