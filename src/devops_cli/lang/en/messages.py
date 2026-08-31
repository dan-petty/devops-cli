"""English localization string catalog for devops-cli."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PersonaTitles:
    devsecops: str = "Principal DevSecOps Engineer"
    architect: str = "Enterprise Infrastructure Architect"
    pm: str = "Enterprise Project Manager"
    auditor: str = "NIST/PCI/SOC Auditor"
    qa: str = "Senior Test Engineer"
    challenger: str = "Principal Adversarial Challenger"


@dataclass(frozen=True)
class ReviewMessages:
    spans_pages: str = "Content spans {count} pages to ensure full coverage."
    generating_metadata: str = "Generating segment metadata..."
    stage_metadata: str = "Analyzing metadata across {count} file(s)..."
    stage_segment: str = "Reviewing {count} file(s)..."
    stage_validate: str = "Validating findings for {count} file(s)..."
    stage_compose: str = "Composing final review..."
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
    updated_finding_status: str = "Updated finding #{index} status → {status}"
    total_sessions_count: str = "[bold]Total Sessions:[/bold]  {count}"
    total_findings_count: str = "[bold]Total Findings:[/bold]  {count}\n"
    review_posted_pr: str = "Review posted as comment on PR #{number}"
    no_findings_session: str = "No findings.json in session {name}"
    session_not_found: str = "Session not found matching: {session}"
    no_findings_to_export: str = "No {status} findings found to export under {target}."
    exported_findings: str = "Exported {count} {status} finding(s) → [bold]{path}[/bold]"
    index_out_of_bounds: str = "Index out of bounds (1-{max_index})"


@dataclass(frozen=True)
class AIMessages:
    provider_model_info: str = "Provider: {provider}  Model: {model}"
    test_success: str = "✓ {reply}"
    test_failed: str = "✗ Failed: {exc}"
    testing_ollama_servers: str = (
        "Testing Ollama servers ({count}) | model: [cyan]{model}[/cyan]..."
    )
    ollama_endpoint_pass: str = "  [cyan]{url}[/cyan]: [green]✓ {ans}[/green] [dim]({wall})[/dim]"
    ollama_endpoint_fail: str = "  [cyan]{url}[/cyan]: [red]✗ failed: {ans}[/red]"
    token_budget_title: str = "AI Context Token Budget Report"
    fits_budget_yes: str = "✓ Yes"
    fits_budget_no: str = "✗ No (Exceeds budget)"
    cache_title: str = "LLM Response Cache Performance"
    cache_cleared: str = "Cleared {count} LLM response cache entries."
    generating_agents: str = "Generating {target} via LLM..."
    written_file: str = "✓ Written: {path}"
    interactive_prompt_header: str = "devops ai chat ({provider} / {model})"
    interactive_prompt_help: str = "Type your message and press Enter. Ctrl+C or exit to quit.\n"
    you_prompt: str = "You: "


@dataclass(frozen=True)
class BenchmarkMessages:
    evaluating_model: str = "Evaluating {model} across {task_count} benchmarks..."
    benchmark_complete: str = "Benchmark evaluation completed for {model}."


@dataclass(frozen=True)
class ConfigMessages:
    header: str = "devops-cli configuration"
    key_col: str = "Key"
    val_col: str = "Value"
    not_set: str = "not set"
    set_success: str = "✓ Set {key} = {value}"
    set_secret_success: str = "✓ Set {key} in OS keyring"


@dataclass(frozen=True)
class InstallMessages:
    status_title: str = "DevOps Tool Status"
    checking_tools: str = "Checking DevOps toolchain versions..."
    fetching_latest: str = "Fetching latest version for [cyan]{name}[/cyan]..."
    installing_tool: str = "Installing [cyan]{name}[/cyan] {version}..."
    tool_installed: str = "✓ {name} {version} installed to {path}"
    tool_already_installed: str = "✓ {name} is already installed ({version})"
    download_failed: str = "Error downloading {name} from {url}: {exc}"
    path_hint: str = (
        'Note: {path} is not in your PATH.\nAdd to your shell config:  export PATH="{path}:$PATH"'
    )


@dataclass(frozen=True)
class GeneralMessages:
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
    elapsed_time: str = "Elapsed: {elapsed:.2f}s"


@dataclass(frozen=True)
class BranchMessages:
    invalid_ticket_id: str = "Invalid ticket ID '{ticket_id}'. Expected format: PROJ-123"
    not_a_git_repo: str = "Not a git repository: {repo_path}"
    created_branch: str = "Created and checked out: {branch_name}"
    no_merged_branches: str = "No merged branches to clean."


@dataclass(frozen=True)
class WorkspaceMessages:
    workspace_synced: str = "Workspace file synchronized with all cloned repositories: {path}"
    generated_workspace: str = "✓ Generated multi-root workspace file at {path}"
    synced_repos: str = "✓ Synced workspace with {count} repo(s)"
    no_repos_found: str = "No cloned repos found under {base_dir}."
    added_folder: str = "Added: {path}"
    removed_folder: str = "Removed: {path}"
    generated_with_count: str = "Generated {ws_file} with {count} folders."
    pruning_stale: str = "Pruning artifacts older than {days} days under .data/..."
    cleaned_artifacts: str = (
        "✓ Cleaned {files} files and {dirs} directories ({freed_mb:.2f} MB freed)."
    )
    data_tier_clean: str = "✓ Data tier is clean; no stale artifacts found."
    outside_boundary: str = "Cannot write workspace file '{path}' outside boundary."


@dataclass(frozen=True)
class RepoMessages:
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
    cloning_repo: str = "Cloning [dim]{url}[/dim] → [dim]{dest}[/dim]"
    already_exists: str = "Repository already exists at {dest}"
    repos_dir_not_found: str = "Repos directory not found: {root}"
    skip_path_traversal: str = "skip {name} (path traversal detected)"
    skip_already_exists: str = "skip {name} (already exists)"
    sync_done: str = "done {name}"
    sync_fail: str = "fail {name}: {exc}"


@dataclass(frozen=True)
class K8sMessages:
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
    applying_tls_secret: str = (
        "[bold]Applying TLS secret '[cyan]{secret}[/cyan]' across cluster namespaces...[/bold]"
    )
    validating_manifests: str = (
        "Validating Kubernetes manifests at '{path}' (k8s: {k8s_version})..."
    )
    applying_manifest: str = "[bold]Applying manifest {name}...[/bold]"
    installing_release: str = "[bold]Installing {name}...[/bold]"


@dataclass(frozen=True)
class AnalyzeMessages:
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


@dataclass(frozen=True)
class DocsMessages:
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


@dataclass(frozen=True)
class ReleaseMessages:
    bumped_version: str = "Bumped version to {version}"
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
    branch_ready: str = "Branch '{branch}' is ready. You can manually open the PR on GitHub."
    changelog_version_diff: str = "Warning: Latest CHANGELOG.md version ({changelog_ver}) differs from pyproject version ({pyproject_ver})"
    working_tree_dirty: str = (
        "Git working directory is dirty. Commit or stash changes before releasing."
    )
    docs_out_of_sync: str = "Documentation is out of sync. Run 'devops release prepare' or 'devops docs generate --sync-readme'"
    running_ci_gate: str = "Running CI quality gate..."
    ci_gate_failed: str = "CI Quality Gate checks failed. Resolve errors before releasing."
    cannot_determine_version: str = "Could not determine target release version."
    push_branch_failed: str = "Warning: Could not push branch to remote: {stderr}"


@dataclass(frozen=True)
class TfMessages:
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
    tflint_executing: str = "Executing TFLint static analysis on '{target}'..."
    tflint_passed: str = "✓ No Terraform / OpenTofu lint issues detected."


@dataclass(frozen=True)
class RemoteCIMessages:
    no_runs_found: str = "No GitHub Actions workflow runs found."
    no_checks_found: str = "No CI checks found for PR #{number}."
    fetching_runs: str = "Fetching remote CI workflow runs..."
    fetching_logs: str = "Fetching CI failure logs for run {run_id}..."
    watching_ci: str = "Watching remote CI runs for PR #{number} (poll interval: {interval}s)..."
    ci_passed: str = "✓ All remote CI checks passed successfully."
    ci_failed: str = "✗ Remote CI checks failed or contains errors."


@dataclass(frozen=True)
class PRMessages:
    list_title: str = "Pull Requests ({state})"
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
    pr_created_success: str = (
        "Pull request created successfully targeting base [bold]{target}[/bold]: {url}"
    )
    pr_updated_success: str = "Successfully updated PR #{number}"


@dataclass(frozen=True)
class UVMessages:
    no_version_provided: str = "No Python version provided and .python-version is missing."
    invalid_version_format: str = "Invalid Python version format: {version}"
    missing_command: str = "Missing command. Example: devops uv run -- pytest -q"


@dataclass(frozen=True)
class DryRunMessages:
    command_response_header: str = "[yellow][dry-run][/yellow] Command response:"
    would_run_command: str = "[yellow][dry-run][/yellow] Would run command: [cyan]{command}[/cyan]"
    would_run_delegated: str = (
        "[yellow][dry-run][/yellow] Would run delegated command: [cyan]{command}[/cyan]"
    )
    skipped_pr_comment: str = "\n[dry-run] Skipped posting comment to PR #{number}"


@dataclass(frozen=True)
class TelemetryMessages:
    status_title: str = "OpenTelemetry Observability Status"
    port_forward_tip: str = (
        "[dim]Port-forward if running in cluster: devops k8s port-forward otel[/dim]"
    )
    view_traces_jaeger: str = "\n[dim]To view traces in Jaeger UI: {url}[/dim]"
    emitting_span: str = (
        "[bold]Emitting test trace span '[cyan]{name}[/cyan]' to [cyan]{endpoint}[/cyan]...[/bold]"
    )
    span_emitted_success: str = "Test span emitted successfully! (Span ID: [cyan]{span_id}[/cyan], Duration: {elapsed_ms:.1f}ms)"
    view_jaeger_service: str = "[dim]View in Jaeger: {url} (Service: {service})[/dim]"
    jaeger_ui_link: str = "[bold]Jaeger Tracing UI:[/bold] [link={url}]{url}[/link]"


@dataclass(frozen=True)
class ScanMessages:
    no_flaws_found: str = "No security vulnerabilities, secrets, or flaws found."
    trivy_executing: str = "Executing Trivy security scan on '{target}' (type: {scan_type})..."
    trivy_passed: str = "✓ No vulnerabilities, secrets, or flaws found by Trivy."
    gitleaks_executing: str = "Executing Gitleaks secret scan on '{target}'..."
    gitleaks_passed: str = "✓ No secrets or credential leaks detected."
    semgrep_executing: str = "Executing Semgrep AST scan on '{target}' (config: {config})..."
    semgrep_passed: str = "✓ No static AST pattern flaws detected."
    checkov_executing: str = "Executing Checkov IaC scan on '{target}'..."
    checkov_passed: str = "✓ No IaC policy violations detected."


@dataclass(frozen=True)
class RAGMessages:
    operation_cancelled: str = "[dim]Operation cancelled.[/dim]"
    reset_cache_success: str = "Reset local indexing cache"
    cannot_connect_qdrant: str = (
        "Cannot connect to Qdrant at [bold]{url}[/bold]\n"
        "Tip: Deploy or start Qdrant via 'devops k8s deploy-stack llm'"
    )
    searching_qdrant: str = "Searching Qdrant ({coll}) for query: '{query}' (limit: {limit})..."
    indexing_complete: str = (
        "Indexing complete! Indexed [cyan]{indexed}[/cyan] file(s), "
        "upserted [cyan]{chunks}[/cyan] chunk(s)"
        "{removed} (skipped {skipped} unchanged files)."
    )
    kb_indexing_complete: str = (
        "Knowledge Base indexing complete! Indexed [cyan]{files}[/cyan] KB file(s), "
        "upserted [cyan]{chunks}[/cyan] chunk(s) into [magenta]{coll}[/magenta]."
    )
    cleared_collection: str = "Cleared collection: {coll}"
    no_matching_query: str = "No matching code/documentation found for query: {query}"


@dataclass(frozen=True)
class TLSMessages:
    cert_generated: str = "Generated leaf certificate: {cert}"
    generating_bundle: str = "[bold]Generating homelab TLS bundle...[/bold]"
    deploying_secret: str = (
        "[bold]Deploying TLS secret '[cyan]{secret}[/cyan]' to Kubernetes namespaces...[/bold]"
    )
    verified_valid: str = "Verified: [cyan]{cert}[/cyan] is valid and signed by [cyan]{ca}[/cyan]"


@dataclass(frozen=True)
class SSHMessages:
    key_generated: str = "Generated Ed25519 SSH keypair: {path}"
    no_managed_keys: str = "No managed SSH keys found. Run 'devops ssh generate' first."
    no_managed_keys_pattern: str = (
        "No managed SSH keys found (expected: [prefix-]id_ed25519-YYYYMMDD)."
    )
    registered_and_configured: str = "Registered new key and updated git signing config."
    cleaned_unregistered_keys: str = (
        "Cleaned up un-registered key files. Fix auth and re-run rotation."
    )
    configured_signing: str = (
        "Configured [dim]gpg.format=ssh[/dim] and [dim]commit.gpgsign=true[/dim]"
    )
    register_tip: str = "\nRun [bold]devops ssh register[/bold] to add it to GitHub."
    registered_on_github: str = "Registered [bold]{title}[/bold] on GitHub (auth + signing)."
    key_age_status: str = "Active key:  [bold cyan]{name}[/bold cyan]"
    key_age_days: str = "Age:         [bold]{age}[/bold] days"
    rotation_needed: str = "Key is {age} days old — rotating..."
    rotation_not_needed: str = (
        "Key is {age} days old (rotation at {rotation_days}d). No rotation needed."
    )
    days_remaining: str = "Rotation:    {days} days remaining"
    rotation_overdue: str = "Rotation:    overdue by {days} days — run 'devops ssh rotate'"
    grace_period_notice: str = "\nOld key {name} remains active for {grace_days} grace days. Remove manually from GitHub when ready."
    new_key_already_exists: str = "New key already exists: {path}"


@dataclass(frozen=True)
class PrometheusMessages:
    query_instant_header: str = "Prometheus Instant Query: '{query}'"
    url_not_configured: str = (
        "Prometheus URL not configured. Run: devops config set prometheus.url <url>"
    )
    no_results: str = "No results."
    expr_header: str = "[bold]{expr}[/bold]"
    series_points_count: str = "{series_count} series, {points_count} total data points"
    series_item: str = "  [cyan]{label}[/cyan]: {points_count} points"


@dataclass(frozen=True)
class ToolMessages:
    working_tree_clean: str = "Working tree clean."
    no_unstaged_changes: str = "No unstaged changes."
    no_pods_in_namespace: str = "No pods found in namespace {namespace}."
    no_argo_apps: str = "No ArgoCD applications found."
    argo_app_not_found: str = "ArgoCD application '{app_name}' not found."
    no_trivy_flaws: str = "No vulnerabilities, secrets, or flaws found by Trivy."


@dataclass(frozen=True)
class ArgoMessages:
    url_not_configured: str = "ArgoCD URL not configured. Run: devops config set argocd.url <url>"
    no_apps_found: str = "No ArgoCD applications found."
    app_not_found: str = "Application '{name}' not found."
    sync_triggered: str = "Sync triggered for '{name}'."
    workflow_submitted: str = "Workflow submitted: {name}"
    workflow_resumed: str = "Workflow resumed: {name}"
    workflow_stopped: str = "Workflow stopped: {name}"
    rollout_restarted: str = "Rollout restarted: {name}"
    rollout_unpaused: str = "Rollout unpaused: {name}"
    rollout_aborted: str = "Rollout aborted: {name}"
    rollout_retry_initiated: str = "Rollout retry initiated: {name}"
    table_title_apps: str = "ArgoCD Applications"
    table_title_workflows: str = "Argo Workflows"
    table_title_rollouts: str = "Argo Rollouts"


@dataclass(frozen=True)
class CIMessages:
    python_version_check: str = "python version check (3.14+)"
    pytest_coverage: str = "pytest & coverage"
    ruff_check: str = "ruff check"
    ruff_format: str = "ruff format"
    mypy_check: str = "mypy (py314 strict)"
    uv_audit: str = "uv audit"
    bandit_scan: str = "bandit security scan"
    actionlint: str = "actionlint (github workflows)"
    docs_validation: str = "docs validation"
    ci_summary_title: str = "CI Summary"
    col_check: str = "Check"
    col_result: str = "Result"
    python_version_fail: str = "Strict Python {required}+ requirement failed. Current: {current}"


@dataclass(frozen=True)
class DevcontainerMessages:
    already_exists: str = "devcontainer.json already exists: {path}"
    created_file: str = "Created: {path}"
    no_manifest_found: str = "No devcontainer.json found: {path}"
    manifest_valid: str = "✓ DevContainer manifest is valid: {path}"
    manifest_validation_failed: str = "✗ DevContainer manifest validation failed for {path}:"
    status_table_title: str = "Devcontainer Status"
    col_repository: str = "Repository"
    status_configured: str = "✓ configured"
    status_missing: str = "✗ missing"
    post_create_start: str = "Running DevContainer post-create setup for {workspace}..."
    post_create_ready: str = "✓ DevContainer post-create setup ready."
    post_start_start: str = "Running DevContainer post-start lifecycle for {workspace}..."
    post_start_ready: str = "✓ DevContainer post-start lifecycle complete."
    updated_image: str = "Updated image → python:{version}"
    mount_permissions_configured: str = "Configured volume mount permissions at {path}"
    temp_dir_permissions_configured: str = (
        "Configured temporary directory permissions (1777) at {path}"
    )


@dataclass(frozen=True)
class DockerMessages:
    table_title_images: str = "Docker Images"
    building_from: str = "Building from [dim]{context}[/dim]..."
    built_image: str = "Built: {short_id}{suffix}"
    pushing_image: str = "Pushing [dim]{image}[/dim]..."
    pushed_success: str = "Pushed."
    pruned_success: str = "Pruned. Space reclaimed: {mb} MB"
    analyzing_layers: str = "Analyzing container image layers for '{image}' via Dive..."
    efficiency_summary: str = (
        "Efficiency: {eff:.1f}% | Size: {size:.1f} MB | Wasted: {wasted:.1f} MB"
    )
    table_title_layers: str = "Container Layer Efficiency: {image}"


@dataclass(frozen=True)
class GrafanaMessages:
    url_not_configured: str = "Grafana URL not configured. Run: devops config set grafana.url <url>"
    table_title_dashboards: str = "Grafana Dashboards"
    exported_success: str = "Exported → {dest}"
    imported_success: str = "Imported: {slug}"
    dir_not_found: str = "Dashboard directory '{path}' not found."
    no_json_files: str = "No dashboard JSON files found in '{path}'."
    synced_dashboard: str = "Synced dashboard: [bold]{title}[/bold] ({file})"
    sync_completed: str = "Dashboard sync completed: {synced}/{total} synced successfully."
    table_title_search: str = "Grafana Search: {query}"
    table_title_datasources: str = "Grafana Datasources"
    table_title_alerts: str = "Grafana Alert Rules"


@dataclass(frozen=True)
class MCPMessages:
    starting_sse: str = "Starting FastMCP server (SSE) on http://{host}:{port}..."
    starting_stdio: str = "Starting FastMCP server (stdio) — devops-cli\n"
    table_title_tools: str = "Registered FastMCP Tools (devops-cli)"
    col_tool_name: str = "MCP Tool Name"
    col_description: str = "Description"


@dataclass(frozen=True)
class ServeMessages:
    starting_service: str = "Starting DevOps CLI REST & OpenAPI Service v{version}"
    listening_on: str = "  [cyan]•[/cyan] Listening on: [bold]http://{host}:{port}[/bold]"
    swagger_ui: str = "  [cyan]•[/cyan] Swagger UI:  [link=http://{host}:{port}/docs]http://{host}:{port}/docs[/link]"
    redoc: str = "  [cyan]•[/cyan] ReDoc:       [link=http://{host}:{port}/redoc]http://{host}:{port}/redoc[/link]"
    openapi_json: str = "  [cyan]•[/cyan] OpenAPI JSON:[link=http://{host}:{port}/openapi.json]http://{host}:{port}/openapi.json[/link]"
    health_endpoint: str = "  [cyan]•[/cyan] Health:      [link=http://{host}:{port}/health]http://{host}:{port}/health[/link]"
    metrics_endpoint: str = "  [cyan]•[/cyan] Metrics:     [link=http://{host}:{port}/metrics]http://{host}:{port}/metrics[/link]\n"


@dataclass(frozen=True)
class PipelineMessages:
    executing: str = "Executing Dagger pipeline from '{path}'..."
    success: str = "✓ Pipeline execution completed successfully ({name})."
    failed: str = "Pipeline execution failed with exit code {code}."
    dagger_not_found: str = (
        "Dagger CLI binary not found in PATH. Install Dagger to run containerized pipelines."
    )


@dataclass(frozen=True)
class TestMessages:
    starting_load_test: str = (
        "Starting k6 load test with {vus} VUs for {duration} ({script_path})..."
    )
    load_test_success: str = "✓ Load test finished successfully ({duration}, {vus} VUs)."
    load_test_failed: str = "Load test failed with exit code {code}."
    k6_not_found: str = "k6 binary not found in PATH. Install k6 (e.g. apt install k6 or brew install k6) to run load tests."


@dataclass(frozen=True)
class LanguageCatalog:
    persona_titles: PersonaTitles = field(default_factory=PersonaTitles)
    messages: GeneralMessages = field(default_factory=GeneralMessages)
    review: ReviewMessages = field(default_factory=ReviewMessages)
    ai: AIMessages = field(default_factory=AIMessages)
    benchmark: BenchmarkMessages = field(default_factory=BenchmarkMessages)
    config: ConfigMessages = field(default_factory=ConfigMessages)
    install: InstallMessages = field(default_factory=InstallMessages)
    branches: BranchMessages = field(default_factory=BranchMessages)
    workspace: WorkspaceMessages = field(default_factory=WorkspaceMessages)
    repos: RepoMessages = field(default_factory=RepoMessages)
    k8s: K8sMessages = field(default_factory=K8sMessages)
    analyze: AnalyzeMessages = field(default_factory=AnalyzeMessages)
    docs: DocsMessages = field(default_factory=DocsMessages)
    release: ReleaseMessages = field(default_factory=ReleaseMessages)
    tf: TfMessages = field(default_factory=TfMessages)
    tofu: TfMessages = field(default_factory=TfMessages)
    remote_ci: RemoteCIMessages = field(default_factory=RemoteCIMessages)
    pr: PRMessages = field(default_factory=PRMessages)
    uv: UVMessages = field(default_factory=UVMessages)
    dry_run: DryRunMessages = field(default_factory=DryRunMessages)
    telemetry: TelemetryMessages = field(default_factory=TelemetryMessages)
    scan: ScanMessages = field(default_factory=ScanMessages)
    rag: RAGMessages = field(default_factory=RAGMessages)
    tls: TLSMessages = field(default_factory=TLSMessages)
    ssh: SSHMessages = field(default_factory=SSHMessages)
    prometheus: PrometheusMessages = field(default_factory=PrometheusMessages)
    tools: ToolMessages = field(default_factory=ToolMessages)
    argo: ArgoMessages = field(default_factory=ArgoMessages)
    ci: CIMessages = field(default_factory=CIMessages)
    devcontainer: DevcontainerMessages = field(default_factory=DevcontainerMessages)
    docker: DockerMessages = field(default_factory=DockerMessages)
    grafana: GrafanaMessages = field(default_factory=GrafanaMessages)
    mcp: MCPMessages = field(default_factory=MCPMessages)
    serve: ServeMessages = field(default_factory=ServeMessages)
    pipeline: PipelineMessages = field(default_factory=PipelineMessages)
    test: TestMessages = field(default_factory=TestMessages)


MESSAGES = LanguageCatalog()
