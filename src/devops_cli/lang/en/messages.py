"""English localization string catalog for devops-cli."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PersonaTitles(BaseModel):
    model_config = ConfigDict(frozen=True)

    devsecops: str = "Principal DevSecOps Engineer"
    architect: str = "Enterprise Infrastructure Architect"
    pm: str = "Enterprise Project Manager"
    auditor: str = "NIST/PCI/SOC Auditor"
    qa: str = "Senior Test Engineer"


class ReviewMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    spans_pages: str = "Content spans {count} pages to ensure full coverage."
    generating_metadata: str = "Generating segment metadata..."
    step1_metadata: str = "Step 1/4: Analyzing metadata across {count} file(s)..."
    step2_segment: str = "Step 2/4: Reviewing {count} file(s)..."
    step3_validate: str = "Step 3/4: Validating findings for {count} file(s)..."
    step4_compose: str = "Step 4/4: Composing final review..."
    segment_progress: str = "  ✓ segment {index}/{total} in {elapsed:.1f}s"
    segment_progress_dryrun: str = "  ✓ segment {index}/{total} (dry-run)"
    segment_validate_progress: str = (
        "  ✓ segment {index}/{total} in {elapsed:.1f}s: {verified}/{findings} finding(s) verified"
    )
    total_elapsed: str = "  total {elapsed:.1f}s"
    collecting_files: str = "Collecting {pattern} files under {target}..."
    no_files_found: str = "No files found."
    diffing_branches: str = "Diffing {branch} against {base}..."
    no_diff_found: str = "No differences found between branches."
    fetching_pr: str = "Fetching PR #{number} from {repo}..."
    findings_saved: str = "  ✓ findings saved → {path}"
    review_saved: str = "Review saved → {path}"
    outside_boundary: str = "Error: Target path '{target}' is outside allowed boundaries."
    exceeds_max_size: str = "Error: Target file '{target}' exceeds maximum size ({max_mb}MB)."
    git_diff_failed: str = "git diff failed: {error}"
    detect_branch_failed: str = (
        "Could not detect branch. Ensure command is run inside a valid git repo."
    )
    github_repo_parse_failed: str = "Could not parse GitHub repo owner/name from remote URL: {raw}"
    github_token_not_configured: str = (
        "GitHub token not configured. Run: devops config set github.token <token>"
    )
    no_review_sessions_found: str = "No review sessions found in .data/reviews/"
    no_findings_to_update: str = "Session has no findings to update."
    specify_index_or_title: str = "Must specify --index <N> or --title <pattern>"
    invalid_status_choices: str = (
        "Status must be one of: VERIFIED, INVALIDATED, MITIGATED, UNVERIFIED"
    )
    no_review_dir_found: str = "No review directory found."
    no_saved_sessions: str = "No saved review sessions found."


class AIMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_model_info: str = "Provider: {provider}  Model: {model}"
    test_success: str = "✓ {reply}"
    test_failed: str = "✗ Failed: {exc}"
    generating_agents: str = "Generating {target} via LLM..."
    written_file: str = "✓ Written: {path}"
    interactive_prompt_header: str = "devops ai chat ({provider} / {model})"
    interactive_prompt_help: str = "Type your message and press Enter. Ctrl+C or exit to quit.\n"
    you_prompt: str = "You: "


class ConfigMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    header: str = "devops-cli configuration"
    key_col: str = "Key"
    val_col: str = "Value"
    not_set: str = "not set"
    set_success: str = "✓ Set {key} = {value}"
    set_secret_success: str = "✓ Set {key} in OS keyring"


class InstallMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    checking_tools: str = "Checking DevOps toolchain versions..."
    installing_tool: str = "Installing {name} ({version})..."
    tool_installed: str = "✓ {name} {version} installed to {path}"
    tool_already_installed: str = "✓ {name} is already installed ({version})"
    download_failed: str = "Error downloading {name} from {url}: {exc}"


class GeneralMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    goodbye: str = "Goodbye."
    llm_unavailable_template_fallback: str = "LLM unavailable ({exc}), falling back to template."
    llm_failed_template_fallback: str = "LLM failed ({exc}), using template."
    target_path_outside_repo: str = "Error: Target path '{dest}' is outside repository boundary."
    key_already_exists: str = "Key already exists: {key_path}"
    generated_key: str = "Generated: {key_path}"
    public_key_path: str = "Public key: {pub_path}"
    no_ssh_key_found: str = "No managed SSH key found. Run 'devops ssh generate' first."
    public_key_not_found: str = "Public key not found: {pub_path}"
    failed_to_register_key: str = "Failed to register key on GitHub: {error}"
    gh_auth_refresh_tip: str = (
        "Tip: run 'gh auth refresh -h github.com -s admin:public_key,write:ssh_signing_key' "
        "and retry."
    )
    vscode_cli_unavailable: str = "Workspace updated, but VS Code CLI is not available to reload."
    invalid_url_scheme: str = "Invalid {purpose} URL: must use http:// or https:// with a hostname."
    refusing_non_public_url: str = (
        "Refusing non-public {purpose} URL. "
        "Set DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true to override."
    )


class BranchMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    invalid_ticket_id: str = "Invalid ticket ID '{ticket_id}'. Expected format: PROJ-123"
    not_a_git_repo: str = "Not a git repository: {repo_path}"
    created_branch: str = "Created and checked out: {branch_name}"
    no_merged_branches: str = "No merged branches to clean."


class WorkspaceMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_workspace: str = "✓ Generated multi-root workspace file at {path}"
    synced_repos: str = "✓ Synced workspace with {count} repo(s)"
    no_repos_found: str = "No cloned repos found under {base_dir}."
    added_folder: str = "Added: {path}"
    removed_folder: str = "Removed: {path}"
    generated_with_count: str = "Generated {ws_file} with {count} folders."


class RepoMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_org_configured: str = (
        "No GitHub organisation configured. Set github.default_org or pass an org name."
    )
    cloning_org_repos: str = "Cloning [bold]{count}[/bold] repos into [dim]{dest}[/dim]"
    already_cloned: str = "Already cloned at {dest}"
    github_token_not_configured: str = (
        "GitHub token not configured. Run 'devops config init' or "
        "set github.token in 'devops config set'"
    )
    invalid_dest_path: str = "Invalid repository destination path."
    invalid_url_hyphen: str = "Invalid repository URL: must not start with a hyphen."
    no_repos_found: str = "No repositories found."
    done: str = "Done."


class K8sMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_context: str = "Current Kubernetes context: [bold cyan]{context}[/bold cyan]"
    switched_context: str = "✓ Switched to Kubernetes context: [bold green]{context}[/bold green]"
    no_contexts_found: str = "No Kubernetes contexts found in Kubeconfig."
    cluster_not_reachable: str = "Kubernetes cluster is not reachable."
    start_minikube_tip: str = "Start it with: [cyan]minikube start --driver=docker[/cyan]"
    starting_minikube: str = "[bold cyan]Starting minikube cluster...[/bold cyan]"
    failed_start_minikube: str = "Failed to start minikube cluster."
    minikube_not_running: str = (
        "minikube is not running. Start with: minikube start --driver=docker"
    )
    adding_helm_repos: str = "[bold]Adding Helm repositories...[/bold]"
    removing_stack_namespaces: str = "[bold]Removing all stack namespaces...[/bold]"
    removing_infra_namespaces: str = "[bold]Removing infra namespaces...[/bold]"
    removing_llm_namespace: str = "[bold]Removing llm namespace...[/bold]"
    kube_linter_passed: str = "Kube-linter audit passed: no security warnings."
    popeye_executing: str = "[dim]Executing Popeye K8s cluster health sanitizer...[/dim]"
    popeye_passed: str = "Popeye cluster audit passed: no health warnings."
    pluto_passed: str = "Pluto API check passed: no deprecated K8s APIs."
    generating_homelab_tls: str = "[bold]Generating Homelab TLS certificate bundle...[/bold]"


class AnalyzeMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_help: str = (
        "Analyze codebases and create/update structured metadata files under .data/analysis/."
    )
    path_help: str = (
        "Analyze a local directory path or single file and save metadata to .data/analysis/."
    )
    branch_help: str = (
        "Analyze a git branch diff against base and save metadata to .data/analysis/."
    )
    pr_help: str = "Analyze a GitHub Pull Request and save metadata to .data/analysis/."
    path_not_exists: str = "Path '{path}' does not exist."
    git_branch_failed: str = "Could not determine active git branch."
    github_token_required: str = (
        "GitHub token required. Run: devops config set github.token <token>"
    )
    github_origin_failed: str = "Could not detect GitHub repository origin URL."
    saved_metadata: str = "✓ Analysis metadata saved to [cyan]{path}[/cyan]"
    would_save_metadata: str = (
        "[yellow][dry-run][/yellow] Would write analysis metadata to: [cyan]{path}[/cyan]"
    )
    analysis_complete: str = "\n[bold green]Analysis Complete:[/bold green] [cyan]{title}[/cyan]"
    lbl_target: str = "[bold]Target:[/bold]"
    lbl_total_files: str = "[bold]Total Files:[/bold]"
    lbl_total_lines: str = "[bold]Total Lines:[/bold]"
    lbl_languages: str = "[bold]Languages:[/bold]"
    lbl_enhanced: str = "[bold]Enhanced Metadata:[/bold]"
    lbl_saved_to: str = "[bold]Saved To:[/bold]"
    enhanced_enabled: str = "[green]Enabled (pseudocode, complexity, last_updated)[/green]"


class DocsMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    generating_docs: str = "Generating CLI and architecture documentation in {output_dir}..."
    generated_file: str = "✓ Generated: {path}"
    docs_up_to_date: str = "✓ All documentation files are up to date."
    docs_outdated: str = (
        "✗ Documentation is out of date: {path} has uncommitted changes or differs."
    )
    docs_missing: str = "✗ Missing documentation file: {path}"
    check_failed: str = (
        "Documentation check failed. Run 'devops docs generate' to refresh documentation."
    )
    synced_readme: str = "✓ Synchronized Command Matrix table in {path}"
    unsupported_format: str = (
        "Unsupported documentation format: {format}. Supported: markdown, json"
    )


class ReleaseMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    status_header: str = "DevOps CLI Release Status"
    current_version: str = "Current Version"
    latest_tag: str = "Latest Git Tag"
    working_tree: str = "Working Tree Clean"
    preparing_release: str = "Preparing release version [cyan]{version}[/cyan]..."
    updated_pyproject: str = "✓ Updated pyproject.toml to version [bold]{version}[/bold]"
    updated_init: str = "✓ Updated src/devops_cli/__init__.py to version [bold]{version}[/bold]"
    updated_changelog: str = (
        "✓ Updated CHANGELOG.md with release header [bold][{version}] - {date}[/bold]"
    )
    invalid_version: str = (
        "Invalid semantic version '{version}'. Expected format: X.Y.Z (e.g., 0.1.8)"
    )
    verification_passed: str = "✓ All release verification checks passed successfully."
    verification_failed: str = "✗ Release verification failed: {reason}"
    tag_created: str = "✓ Created git tag [bold]{tag}[/bold]"
    tag_pushed: str = "✓ Pushed commit and tag [bold]{tag}[/bold] to origin"
    notes_not_found: str = "No changelog entry found for version {version} in CHANGELOG.md"
    dry_run_prepare: str = (
        "[yellow][dry-run][/yellow] Would bump version to {version} and sync docs/README"
    )
    dry_run_tag: str = (
        "[yellow][dry-run][/yellow] Would create git tag {tag} and commit release files"
    )
    creating_release_branch: str = "Creating release branch [cyan]{branch}[/cyan]..."
    branch_created: str = "✓ Created and checked out release branch [bold]{branch}[/bold]"
    creating_release_pr: str = "Opening release Pull Request for [cyan]v{version}[/cyan]..."
    pr_created: str = "✓ Created Release Pull Request: [bold green]{url}[/bold green]"
    pr_failed: str = "✗ Failed to create Release Pull Request: {error}"
    dry_run_pr: str = (
        "[yellow][dry-run][/yellow] Would create release branch {branch}, "
        "commit release files, and open Pull Request for v{version}"
    )


class TfMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    init_header: str = "Initializing OpenTofu in [cyan]{path}[/cyan]..."
    init_success: str = "✓ OpenTofu initialization successful."
    plan_header: str = "Running OpenTofu plan for [cyan]{path}[/cyan]..."
    plan_success: str = "✓ OpenTofu plan completed."
    apply_header: str = "Applying OpenTofu configuration in [cyan]{path}[/cyan]..."
    apply_success: str = "✓ OpenTofu apply completed successfully."
    destroy_header: str = "Destroying OpenTofu resources in [cyan]{path}[/cyan]..."
    destroy_success: str = "✓ OpenTofu destroy completed."
    output_header: str = "Retrieving OpenTofu outputs from [cyan]{path}[/cyan]..."
    validate_header: str = "Validating OpenTofu configuration in [cyan]{path}[/cyan]..."
    validate_success: str = "✓ OpenTofu configuration is valid."
    fmt_header: str = "Formatting OpenTofu files in [cyan]{path}[/cyan]..."
    fmt_success: str = "✓ OpenTofu files formatted."
    binary_not_found: str = (
        "Neither 'tofu' nor 'terraform' was found in PATH. "
        "Install OpenTofu or run 'devops install-tools'."
    )
    dir_not_found: str = "OpenTofu directory '{path}' does not exist."
    deploy_cloud_header: str = (
        "Deploying {provider} cloud infrastructure from [cyan]{path}[/cyan]..."
    )
    deploy_cloud_success: str = "✓ {provider} cloud infrastructure deployed successfully."


class RemoteCIMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_runs_found: str = "No GitHub Actions workflow runs found."
    no_checks_found: str = "No CI checks found for PR #{number}."
    fetching_runs: str = "Fetching remote CI workflow runs..."
    fetching_logs: str = "Fetching CI failure logs for run {run_id}..."
    watching_ci: str = "Watching remote CI runs for PR #{number} (poll interval: {interval}s)..."
    ci_passed: str = "✓ All remote CI checks passed successfully."
    ci_failed: str = "✗ Remote CI checks failed or contains errors."


class PRMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_prs_found: str = "No pull requests found matching criteria."
    pr_created: str = "✓ Pull request created: #{number} ({url})"
    pr_updated: str = "✓ Pull request #{number} updated: {url}"
    invalid_base_branch: str = (
        "Invalid PR base branch '{base}'. Per repository governance, feature PRs must target an "
        "active release branch (e.g. release/vX.Y.Z) rather than 'main'."
    )
    gh_cli_required: str = (
        "GitHub CLI ('gh') is required for pull request operations. "
        "Please install gh or ensure it is in PATH."
    )


class UVMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_version_provided: str = "No Python version provided and .python-version is missing."
    invalid_version_format: str = "Invalid Python version format: {version}"
    missing_command: str = "Missing command. Example: devops uv run -- pytest -q"


class DryRunMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_response_header: str = "[yellow][dry-run][/yellow] Command response:"
    would_run_command: str = "[yellow][dry-run][/yellow] Would run command: [cyan]{command}[/cyan]"
    would_run_delegated: str = (
        "[yellow][dry-run][/yellow] Would run delegated command: [cyan]{command}[/cyan]"
    )
    skipped_pr_comment: str = "\n[dry-run] Skipped posting comment to PR #{number}"


class TelemetryMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    port_forward_tip: str = (
        "[dim]Port-forward if running in cluster: devops k8s port-forward otel[/dim]"
    )


class ScanMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_flaws_found: str = "No security vulnerabilities, secrets, or flaws found."


class RAGMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_cancelled: str = "[dim]Operation cancelled.[/dim]"
    reset_cache_success: str = "Reset local indexing cache"


class TLSMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    generating_bundle: str = "[bold]Generating homelab TLS bundle...[/bold]"


class SSHMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_managed_keys: str = "No managed SSH keys found. Run 'devops ssh generate' first."
    no_managed_keys_pattern: str = "No managed SSH keys found (expected: id_ed25519-YYYYMMMDD)."
    registered_and_configured: str = "Registered new key and updated git signing config."
    cleaned_unregistered_keys: str = (
        "Cleaned up un-registered key files. Fix auth and re-run rotation."
    )
    configured_signing: str = (
        "Configured [dim]gpg.format=ssh[/dim] and [dim]commit.gpgsign=true[/dim]"
    )
    register_tip: str = "\nRun [bold]devops ssh register[/bold] to add it to GitHub."


class PrometheusMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    url_not_configured: str = (
        "Prometheus URL not configured. Run: devops config set prometheus.url <url>"
    )
    no_results: str = "No results."


class ToolMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    working_tree_clean: str = "Working tree clean."
    no_unstaged_changes: str = "No unstaged changes."
    no_pods_in_namespace: str = "No pods found in namespace {namespace}."
    no_argo_apps: str = "No ArgoCD applications found."
    no_trivy_flaws: str = "No vulnerabilities, secrets, or flaws found by Trivy."


class LanguageCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    persona_titles: PersonaTitles = PersonaTitles()
    messages: GeneralMessages = GeneralMessages()
    review: ReviewMessages = ReviewMessages()
    ai: AIMessages = AIMessages()
    config: ConfigMessages = ConfigMessages()
    install: InstallMessages = InstallMessages()
    branches: BranchMessages = BranchMessages()
    workspace: WorkspaceMessages = WorkspaceMessages()
    repos: RepoMessages = RepoMessages()
    k8s: K8sMessages = K8sMessages()
    analyze: AnalyzeMessages = AnalyzeMessages()
    docs: DocsMessages = DocsMessages()
    release: ReleaseMessages = ReleaseMessages()
    tf: TfMessages = TfMessages()
    tofu: TfMessages = TfMessages()
    remote_ci: RemoteCIMessages = RemoteCIMessages()
    pr: PRMessages = PRMessages()
    uv: UVMessages = UVMessages()
    dry_run: DryRunMessages = DryRunMessages()
    telemetry: TelemetryMessages = TelemetryMessages()
    scan: ScanMessages = ScanMessages()
    rag: RAGMessages = RAGMessages()
    tls: TLSMessages = TLSMessages()
    ssh: SSHMessages = SSHMessages()
    prometheus: PrometheusMessages = PrometheusMessages()
    tools: ToolMessages = ToolMessages()


MESSAGES = LanguageCatalog()
