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
    segment_progress: str = "  ✓ segment {index}/{total} in {elapsed}"
    segment_progress_dryrun: str = "  ✓ segment {index}/{total} (dry-run)"
    segment_validate_progress: str = (
        "  ✓ segment {index}/{total} in {elapsed}: {verified}/{findings} finding(s) verified"
    )
    total_elapsed: str = "  total {elapsed}"
    collecting_files: str = "Collecting {pattern} files under {target}..."
    no_files_found: str = "No files found."
    diffing_branches: str = "Diffing {branch} against {base}..."
    no_diff_found: str = "No differences found between branches."
    nothing_for_personas: str = (
        "Nothing is left for the personas: every file under review is a lockfile, a planning "
        "document or a generated reference. The secret scan still reads {count} of them."
    )
    nothing_for_personas_unscanned: str = (
        "Nothing is left for the personas: every file under review is a lockfile, a planning "
        "document or a generated reference. The static scan is off, so none of the {count} "
        "is read."
    )
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
    no_review_sessions_found: str = "No review sessions found in {reviews_dir}"
    no_findings_to_update: str = "Session has no findings to update."
    specify_one_finding: str = "Name one finding: --index <N>, --title <pattern> or --candidate <N>"
    title_matches_none: str = "No finding title contains '{pattern}'."
    title_matches_several: str = (
        "Findings {numbers} all contain '{pattern}' in their titles; name one with --index."
    )
    invalid_status_choices: str = (
        "Status must be one of: VERIFIED, INVALIDATED, MITIGATED, UNVERIFIED"
    )
    no_review_dir_found: str = "No review directory found."
    no_saved_sessions: str = "No saved review sessions found."
    updated_finding_status: str = "Updated finding #{index} status → {status}"
    updated_candidate_status: str = "Updated candidate #{index} status → {status}"
    candidate_moved: str = "Candidate #{index} added to findings.json as finding #{number}"
    candidate_already_reported: str = (
        "findings.json already reports candidate #{index}'s defect as finding #{number}; "
        "give the verdict there with --index {number}."
    )
    candidate_copy_ambiguous: str = (
        "Finding #{number} in findings.json reports candidates {candidates}, which share a "
        "persona, title, location and description; give the verdict there with --index {number}, "
        "which records it on each."
    )
    session_write_failed: str = (
        "Cannot write the session's files, so the verdict was not recorded: {error}"
    )
    agent_over_person: str = (
        "A person gave this finding its verdict, and an agent cannot change it; "
        "only --adjudicator human can."
    )
    verdict_teaches_nothing: str = (
        "The verdict is recorded, but later reviews will not suppress this finding: its review "
        "recorded no code at its location, as sessions saved by earlier versions do not, or its "
        "title and description name no identifier of that code."
    )
    sessions_counted: str = (
        "[bold]Sessions:[/bold] {total} (counted {counted}: {repeats} repeat sessions collapsed, "
        "{target_only} target-only, {unkeyed} unkeyed)"
    )
    total_findings_count: str = "[bold]Total Findings:[/bold]  {count}\n"
    review_posted_pr: str = "Review posted as comment on PR #{number}"
    no_findings_session: str = "No findings.json in session {name}"
    session_not_found: str = "Session not found matching: {session}"
    no_findings_to_export: str = (
        "No {status} findings under {target} that {path} does not already hold; it is unchanged."
    )
    exported_findings: str = "Appended {count} {status} finding(s) → [bold]{path}[/bold]"
    index_out_of_bounds: str = "Index out of bounds (1-{max_index})"
    table_title_findings: str = "Code Review Findings"
    table_title_dependencies: str = "[bold yellow]External Dependencies Audit[/bold yellow]"
    table_title_network_references: str = (
        "[bold yellow]Network & Egress References Audit[/bold yellow]"
    )
    summary: str = "[bold]Summary[/bold]"


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
    harness_title: str = "Agent Harness Slots"
    harness_offload_title: str = "Sub-Agent Local Offload"
    default_quiesce_reason: str = "Operator requested emergency quiesce"
    quiesce_dry_run: str = "[DRY RUN] Quiesce simulated: {badge} | Reason: {reason}"
    quiesce_executed: str = "Quiesce flag set: {badge} | Reason: {reason}"
    failover_dry_run: str = "[DRY RUN] Failover simulated: {badge} -> {target}"
    failover_executed: str = (
        "Fallback recorded: {badge} -> {target}; `devops ai gateway failover` reroutes requests"
    )
    resume_dry_run: str = "[DRY RUN] Flag not cleared: {badge}"
    constellation_title: str = "Agent Constellation Fleet"
    constellation_flag_only: str = (
        "[dim]This flag records intent only: no running task reads it.[/dim]"
    )


@dataclass(frozen=True)
class BenchmarkMessages:
    evaluating_model: str = "Evaluating {model} across {task_count} benchmarks..."
    benchmark_complete: str = "Benchmark evaluation completed for {model}."
    table_title_leaderboard: str = "AI Benchmark Leaderboard (Session {session_id})"
    table_title_category_breakdown: str = "Domain Category Breakdown (Session {session_id})"
    table_title_server_hardware: str = (
        "Ollama Server Hardware & Node Performance (Session {session_id})"
    )


@dataclass(frozen=True)
class ConfigMessages:
    header: str = "devops-cli configuration"
    key_col: str = "Key"
    val_col: str = "Value"
    not_set: str = "not set"
    set_success: str = "✓ Set {key} = {value}"
    set_secret_success: str = "✓ Set {key} in OS keyring"
    value_required: str = "{key} needs a VALUE; only a credential may be typed at a hidden prompt."
    secret_prompt: str = "{key} (typing hidden)"


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
        "Refusing non-public {purpose} URL. A service URL from your configuration may name a "
        "private address once ai.allow_private_network is true "
        "(DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true); other URLs must be public."
    )
    elapsed_time: str = "Elapsed: {elapsed}"


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
    pruning_stale: str = "Pruning artifacts older than {days} days in {data_dir}..."
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
    table_title_cloned: str = "Cloned repositories — {root}"


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
    rbac_audit_passed: str = (
        "RBAC audit passed: no broad or wildcard role granted to a non-system subject "
        "in {bindings} binding(s)."
    )
    rbac_audit_failed: str = (
        "RBAC audit failed: {violations} overprivileged grant(s) in {bindings} binding(s)."
    )
    rbac_cluster_scope: str = "(cluster)"
    generating_homelab_tls: str = "[bold]Generating Homelab TLS certificate bundle...[/bold]"
    applying_tls_secret: str = (
        "[bold]Applying TLS secret '[cyan]{secret}[/cyan]' across cluster namespaces...[/bold]"
    )
    validating_manifests: str = (
        "Validating Kubernetes manifests at '{path}' (k8s: {k8s_version})..."
    )
    applying_manifest: str = "[bold]Applying manifest {name}...[/bold]"
    installing_release: str = "[bold]Installing {name}...[/bold]"
    table_title_tls_secrets: str = "Kubernetes TLS Secret Deployment"
    table_title_pods: str = "Kubernetes Pods"
    table_title_contexts: str = "Kubernetes Contexts"
    push_unknown_secret: str = "Unknown Secret: {names}. The table holds: {known}."
    push_unknown_stack: str = "Unknown stack '{stack}'. Choose one of: {known}."
    push_namespace_missing: str = "Namespace {namespace} not found: skipped {secret}."
    push_restart_command: str = "Restart skipped (--no-restart): {command}"
    push_failed: str = "Cluster Secrets not pushed; nothing was written. {reason}"
    push_write_failed: str = (
        "Cluster Secret push stopped while writing. Already done: {completed}. {reason} "
        "Fix the cause and rerun; stored keyring values are reused, so nothing is regenerated."
    )
    pushing_secrets: str = "[bold]Pushing cluster Secrets from the keyring...[/bold]"
    push_plan_read: str = (
        "Plan only: read {sources}{context}; wrote nothing. "
        "--dry-run lists the requests without making any."
    )
    push_plan_sources: str = "the keyring and the cluster"
    push_plan_sources_github: str = (
        "the keyring, gh's record of its machine account (gh checks the token on github.com) "
        "and the cluster"
    )
    push_dry_run_heading: str = (
        "Dry run: no request was made. A push would make these requests, in order:"
    )
    push_dry_run_writes: str = (
        "The writes, from the first keyring write on, run only when every key resolves: no "
        "source missing or invalid, and no live value differing without --rotate. "
        "--plan reads the keyring, gh and the cluster to show each key's state."
    )
    job_cronjob_missing: str = (
        "CronJob devops/devops-cli not found. Deploy it first: "
        "devops k8s deploy-stack --stack devops"
    )
    job_created: str = "Created Job {name}. Follow it with: kubectl -n devops logs -f job/{name}"
    job_dry_run_heading: str = (
        "Dry run: no request was made. run-job would make these requests, in order:"
    )
    job_not_started: str = (
        "Job {name} did not start within {seconds:g} s. Inspect it: "
        "kubectl -n devops describe job/{name}"
    )
    job_no_exit_code: str = (
        "Job {name} reported no exit code. Inspect it: kubectl -n devops describe job/{name}"
    )
    table_title_configured_services: str = "Configured Service Targets ({stack})"
    table_title_policy_violations: str = "Kubernetes Policy Violations ({engine})"
    table_title_rbac_audit: str = "Kubernetes RBAC Security Audit"
    table_title_kube_linter: str = "Kube-Linter Manifest Security Checks"
    table_title_popeye: str = "Popeye Cluster Health Sanitizer Audit"
    table_title_pluto: str = "Pluto Deprecated Kubernetes API Version Audit"
    table_title_kubeconform: str = "Kubeconform Strict Schema Validation"
    table_title_nodes: str = "Nodes"
    node_ready: str = "Ready"
    node_not_ready: str = "NotReady"


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
    argv_unresolved: str = "{location} {owner}: 'devops {command_line}': {problem}."
    argv_unknown_command: str = "unknown command '{token}' under '{command_path}'"
    argv_unknown_option: str = "unknown option '{token}' for '{command_path}'"
    argv_unexpected_argument: str = "unexpected extra argument '{token}' for '{command_path}'"
    synced_readme: str = "✓ Synchronized Command Matrix table in {path}"
    unsupported_format: str = (
        "Unsupported documentation format: {format}. Supported: markdown, json"
    )
    compacting_docs: str = "Compacting documentation for series [cyan]{series}[/cyan]..."
    compacted_success: str = (
        "✓ Successfully compacted documentation for series [bold cyan]{series}[/bold cyan] "
        "({bytes_saved} bytes saved)."
    )
    compacted_up_to_date: str = (
        "✓ Documentation is already compacted for series [cyan]{series}[/cyan]."
    )
    compact_check_failed: str = (
        "✗ Documentation compaction required for series [bold red]{series}[/bold red]. "
        "Run 'devops docs compact --series {series}' to compact."
    )
    archive_created: str = "✓ Historical sprint log archived to: {path}"


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
    updated_service_image_tag: str = (
        "✓ Pinned the service image in k8s/devops/kustomization.yaml to [bold]v{version}[/bold]"
    )
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
    notes_in_sync: str = "✓ {tag} already matches CHANGELOG.md"
    notes_republished: str = "✓ Republished {tag} from CHANGELOG.md{stripped}"
    notes_republish_failed: str = "✗ Could not update {tag}"
    notes_unreadable: str = "Skipped {tag}: the published description could not be read"
    notes_no_changelog: str = "Skipped {tag}: no changelog entry"
    notes_details_left_out: str = "Each entry's details are left out to fit GitHub's size limit."
    notes_full_notes: str = "The full notes are in {full_notes}."
    notes_full_notes_linked: str = "[`CHANGELOG.md` at v{version}]({url})"
    notes_full_notes_unlinked: str = "`CHANGELOG.md` at v{version}"
    notes_entries_left_out: str = "Entries left out to fit: {count}."
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
    table_title_graph: str = "IaC Resource Dependency Graph: {directory}"
    table_title_blast_radius: str = "Blast Radius: {address}"
    table_title_drift: str = "Configuration Drift: {directory}"
    graph_summary: str = (
        "{resources} resource(s), {modules} module(s), {edges} dependency edge(s) "
        "across {files} file(s)."
    )
    graph_no_resources: str = "No resources declared in '{directory}'."
    graph_unknown_address: str = "Resource address '{address}' is not declared in '{directory}'."
    blast_radius_summary: str = "{address} impacts {impact} address(es); depends on {depends}."
    drift_no_state: str = "No state file found in '{directory}'; all {declared} declared resource(s) are pending apply."
    drift_in_sync: str = "✓ Configuration and state agree on all {count} resource(s)."
    drift_summary: str = (
        "{missing} declared but not in state, {orphaned} in state but not declared, "
        "{synced} in sync."
    )
    parse_failures: str = "{count} file(s) could not be parsed: {files}"
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
    deploy_cloud_state_in_checkout: str = (
        "{path} has no local state, but the main checkout's {checkout} does. A worktree "
        "does not share the main checkout's untracked state, so init and apply here start "
        "from empty state and plan to create every resource again. Deploy from the main "
        "checkout, or move the state or configure a remote backend first."
    )
    deploy_cloud_state_auto_approve_refused: str = (
        "Refusing to auto-approve a deploy from empty state; run without --auto-approve "
        "to confirm it."
    )
    deploy_cloud_confirm_empty_state: str = "Deploy from empty state anyway?"
    tflint_executing: str = "Executing TFLint static analysis on '{target}'..."
    tflint_passed: str = "✓ No Terraform / OpenTofu lint issues detected."
    table_title_status: str = "OpenTofu Status — {name}"
    table_title_tflint: str = "TFLint Findings: {target}"


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
    monitoring_pr: str = "Monitoring PR #{number} for CI checks and review completion..."
    pr_ready_success: str = "PR #{number} is 100% READY FOR MERGING: All checks passed, reviews complete, 0 unresolved threads."
    pr_marked_ready_success: str = "PR #{number} marked as ready for review."
    pr_already_ready: str = "PR #{number} is already marked ready for review."
    pr_already_merged: str = "PR #{number} is already merged into base branch '{base}'."
    pr_closed_unmerged: str = "PR #{number} is closed without being merged."
    pr_closed_success: str = "PR #{number} closed successfully."
    pr_still_draft_error: str = (
        "PR #{number} is still in draft state after ready conversion command."
    )
    checks_passed: str = "✓ All CI checks passed ({count}/{count} completed successfully)."
    copilot_review_active: str = "Copilot review session is currently active..."
    copilot_review_complete: str = "Copilot review session complete."
    update_branch_success: str = (
        "✓ Successfully updated branch for PR #{number} from base '{base}'."
    )
    update_branch_failed: str = "✗ Failed to update PR #{number}: {error}"
    update_branch_dry_run: str = r"[yellow]\[dry-run][/yellow] Would update PR #{number} ({branch}) with latest commits from '{base}'"
    update_branch_already_up_to_date: str = (
        "PR #{number} branch is already up to date with base '{base}'."
    )
    update_branch_no_prs: str = "No open pull requests found to update."
    update_branch_conflict: str = (
        "✗ Merge conflict detected on PR #{number} with base '{base}'. Manual resolution required."
    )
    update_dispatch_ci_success: str = (
        "✓ Dispatched {workflow} for PR #{number} on branch '{branch}'."
    )
    update_dispatch_ci_head_unchanged: str = (
        "✗ Head SHA for PR #{number} did not change after update; skipped {workflow} dispatch."
    )
    update_dispatch_ci_fork: str = (
        "PR #{number} head branch is in fork '{fork}'; skipped {workflow} dispatch."
    )
    update_dispatch_ci_failed: str = "✗ Failed to dispatch {workflow} for PR #{number}: {error}"
    update_dry_run_heading: str = (
        r"[yellow]\[dry-run][/yellow] Planned external requests to update PR #{number}:"
    )
    update_all_dry_run_heading: str = (
        r"[yellow]\[dry-run][/yellow] Planned external requests to update all open PRs:"
    )
    update_table_title: str = "Pull Request Branch Update Summary"
    grounding_closes_no_issue: str = (
        "PR #{number} is not grounded: its body closes no issue in {repo}. Name the one issue "
        "it delivers with a closing keyword: Closes #<issue>."
    )
    grounding_closes_several_issues: str = (
        "PR #{number} is not grounded: its body closes {count} issues ({issues}), and a PR "
        "delivers exactly one."
    )
    grounding_task_file_missing: str = (
        "PR #{number} is not grounded: it adds, modifies or renames no {pattern} for #{issue}."
    )
    grounding_files_unread: str = (
        "PR #{number} is not grounded: the files it changes could not be read ({error})."
    )
    grounding_tasks_dir_unread: str = (
        "PR #{number} is not grounded: {path}/ could not be read at its base ({error})."
    )
    grounding_release_files_changed: str = (
        "PR #{number} changes {files}: a PR into {base} leaves them to the cut, so open PRs "
        "never conflict on them. Add its changelog entry as {fragment} instead."
    )
    grounding_item_not_in_release: str = (
        "PR #{number} closes #{issue}, which is {placement}, not in {release}: a PR into "
        "{base} delivers an item of {release}, whose scope was fixed when it started."
    )
    grounding_item_in_release: str = "in {release}"
    grounding_item_in_backlog: str = "in the backlog"
    grounding_item_unread: str = (
        "PR #{number} is not grounded: the Release of #{issue} could not be read ({error})."
    )
    changed_files_unread: str = "Could not read the files PR #{number} changes ({error})."


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
    placeholders_note: str = (
        "Values in <angle brackets> are placeholders for what the run would read or make; "
        "no value is shown."
    )


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
    profile_devops_only: str = (
        "telemetry profile runs only a devops-cli command, whose first word is 'devops' "
        "(e.g. 'devops k8s contexts'); pass --trace-id to show a trace already in Jaeger."
    )
    semconv_refreshed: str = (
        "{path} now holds {attributes} attributes, {metrics} metrics and {spans} span types "
        "from {repo}@{commit} (weaver {weaver})."
    )


@dataclass(frozen=True)
class ScanMessages:
    no_flaws_found: str = "No security vulnerabilities, secrets, or flaws found."
    trivy_executing: str = "Executing Trivy security scan on '{target}' (type: {scan_type})..."
    trivy_passed: str = "✓ No vulnerabilities, secrets, or flaws found by Trivy."
    gitleaks_executing: str = "Executing Gitleaks secret scan on '{target}'..."
    gitleaks_passed: str = "✓ No secrets or credential leaks detected."
    semgrep_executing: str = "Executing Semgrep AST scan on '{target}' (config: {config})..."
    semgrep_passed: str = "✓ No static AST pattern flaws detected."
    semgrep_default_flaw: str = "Code pattern flaw detected by Semgrep"
    semgrep_default_message: str = "Code pattern flaw detected by Semgrep"
    semgrep_batch_failed: str = "batch {batch} of {batches}, {files} files: {reason}"
    checkov_executing: str = "Executing Checkov IaC scan on '{target}'..."
    checkov_passed: str = "✓ No IaC policy violations detected."


@dataclass(frozen=True)
class RAGMessages:
    operation_cancelled: str = "[dim]Operation cancelled.[/dim]"
    reset_cache_success: str = "Reset local indexing cache"
    cannot_connect_qdrant: str = (
        "Cannot connect to Qdrant at [bold]{url}[/bold]\n"
        "Tip: Deploy or start Qdrant via 'devops k8s deploy-stack --stack llm'"
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
    stopped_for_run: str = (
        "RAG is off for the rest of this run: {error}. To fix it, serve {model} on a backend, "
        "point ai.tasks.embedding at a backend that serves it, or set ai.rag.enabled: false."
    )
    search_embedding_failed: str = "RAG search unavailable: {error}. Fallback: use search_code."
    lookup_failed: str = (
        "RAG lookup failed, so prompts go on without retrieved context: {error}. Later failures "
        "this run are logged at debug level."
    )
    paused: str = "RAG lookups paused for {seconds}s after {failures} failures: {error}."


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
    table_title_managed_keys: str = "Managed SSH Keys"


@dataclass(frozen=True)
class PrometheusMessages:
    query_instant_header: str = "Prometheus Instant Query: '{query}'"
    table_title_analysis: str = "Series Analysis: {expr}"
    table_title_anomalies: str = "Detected Anomalies"
    no_series_to_analyze: str = "Query '{expr}' returned no series to analyze."
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
    workflow_submitted: str = "Workflow submitted: {name} ({phase})"
    workflow_resumed: str = "Workflow resumed: {name}"
    workflow_stopped: str = "Workflow stopped: {name}"
    rollout_restarted: str = "Rollout restarted: {name}"
    rollout_unpaused: str = "Rollout unpaused: {name}"
    rollout_aborted: str = "Rollout aborted: {name}"
    rollout_retry_initiated: str = "Rollout retry initiated: {name}"
    table_title_apps: str = "ArgoCD Applications"
    table_title_workflows: str = "Argo Workflows"
    table_title_rollouts: str = "Argo Rollouts"
    table_title_rollout_status: str = "Argo Rollout: {name}"
    workflow_finished: str = "Workflow {name} finished with phase: {phase}"
    workflow_no_pods: str = "Workflow '{name}' has no pod nodes to stream logs from."
    workflow_wait_timeout: str = (
        "Timed out after {seconds:.0f}s waiting for workflow '{name}' to reach a terminal phase."
    )


@dataclass(frozen=True)
class CIMessages:
    ci_dry_run_heading: str = (
        "Dry run: no request was made. CI would make these requests, in order:"
    )
    python_version_check: str = "python version check (3.14+)"
    no_covering_tests: str = (
        "No covering tests found for: {files}. Changed code without a covering test "
        "cannot be verified by a narrowed run."
    )
    no_testable_files: str = "No source or test files supplied; nothing to verify."
    selection_fallback: str = (
        "Falling back to the full suite because the changed sources map to no tests."
    )
    selection_empty: str = (
        "Refusing to report success without running any tests. Re-run with --fallback "
        "to verify via the full suite, or add a covering test."
    )
    pytest_coverage: str = "pytest & coverage"
    ruff_check: str = "ruff check"
    ruff_format: str = "ruff format"
    mypy_check: str = "mypy (py314 strict)"
    uv_check: str = "uv check"
    uv_lock: str = "uv lockfile freshness"
    uv_outdated: str = "uv tree --outdated"
    uv_audit: str = "uv audit"
    bandit_scan: str = "bandit security scan"
    actionlint: str = "actionlint (github workflows)"
    docs_validation: str = "docs validation"
    devcontainer_validation: str = "devcontainer validation"
    ci_summary_title: str = "CI Summary"
    col_check: str = "Check"
    col_result: str = "Result"
    python_version_fail: str = "Strict Python {required}+ requirement failed. Current: {current}"
    cache_hit: str = (
        "Codebase unchanged since last verification. Utilizing CI cache (all checks passed)."
    )
    cache_tree_changed: str = (
        "Working tree changed while the gate ran; result not recorded in CI cache."
    )
    gate_root: str = "Quality gate root: {root}"
    gate_root_stale: str = (
        "{root} is a linked git worktree whose git directory is missing, so git-based checks "
        "fail there. If its main checkout moved, run `git worktree repair {root_arg}` from the "
        "main checkout. If the worktree was pruned, repair cannot restore it: move {root} "
        "aside, keeping any uncommitted work, and re-create it with `git worktree add` from "
        "the main checkout."
    )
    gate_root_slow_mount: str = (
        "{root} is on a {fstype} share of a host folder, where each file check takes hundreds "
        "of times longer than on a Linux filesystem, so the tests run several times slower. "
        "Clone the repository into the WSL filesystem or a container volume and reopen it there."
    )
    test_budget_exceeded: str = "Tests took {duration}, over the {budget} budget. Slowest tests:"
    coverage_index_tree_changed: str = (
        "Files changed during the run; index not saved:\n{files}\n"
        "Re-run `devops ci coverage --build-index` on a clean working tree."
    )
    coverage_index_saved: str = "Coverage index built and saved in {duration}."
    coverage_index_age: str = (
        "Coverage index is {age} old ({changed_count} file(s) changed since build)."
    )
    coverage_index_missing: str = (
        "No coverage index found. Run `devops ci coverage --build-index` to build one."
    )
    selection_trigger_full_run: str = (
        "{file} can change the outcome of tests that never import it. "
        "Running the full test suite. Run `devops ci coverage --build-index` to update."
    )
    selection_trigger_refusal: str = (
        "Refusing to narrow tests because {file} changed. Run without --no-fallback "
        "or run the full suite."
    )


@dataclass(frozen=True)
class DevcontainerMessages:
    already_exists: str = "devcontainer.json already exists: {path}"
    auto_deploy_failed: str = (
        "Failed to auto-deploy Kubernetes stack '{stack}'. If the keyring was still locked, run "
        "`devops devcontainer unlock-keyring`, then `devops k8s deploy-stack --stack {stack}`."
    )
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
    bootstrap_k8s_start: str = "Starting background Kubernetes bootstrap for {workspace}..."
    bootstrap_k8s_ready: str = "✓ Background Kubernetes bootstrap complete."
    updated_image: str = "Updated image → python:{version}"
    mount_permissions_configured: str = "Configured volume mount permissions at {path}"
    temp_dir_permissions_configured: str = (
        "Configured temporary directory permissions (1777) at {path}"
    )
    keyring_new_password: str = "New keyring password: "
    keyring_repeat_password: str = "Repeat keyring password: "
    keyring_password: str = "Keyring password: "
    keyring_unlocked: str = "✓ Keyring unlocked; gh, git and devops can store secrets."
    keyring_already_unlocked: str = "Keyring is already unlocked."
    keyring_unlock_skipped: str = (
        "Keyring left locked; the next terminal you open will ask again, or run "
        "`devops devcontainer unlock-keyring`."
    )
    gh_token_moved: str = "✓ Moved the gh token for {host} from hosts.yml into the keyring."


@dataclass(frozen=True)
class DockerMessages:
    table_title_images: str = "Docker Images"
    table_title_containers: str = "Docker Containers"
    table_title_stats: str = "Docker Container Stats"
    building_from: str = "Building from [dim]{context}[/dim]..."
    built_image: str = "Built: {short_id}{suffix}"
    pushing_image: str = "Pushing [dim]{image}[/dim]..."
    pushed_success: str = "Pushed."
    pruned_success: str = "Pruned. Space reclaimed: {mb} MB"
    analyzing_layers: str = "Analyzing container image layers for '{image}' via Dive..."
    layer_analysis_not_run: str = "Dive layer analysis {status}: {reason}"
    efficiency_summary: str = (
        "Efficiency: {eff:.1f}% | Size: {size:.1f} MB | Wasted: {wasted:.1f} MB"
    )
    table_title_layers: str = "Container Layer Efficiency: {image}"
    table_title_build_cache: str = "BuildKit Layer Cache"
    build_cache_summary: str = (
        "Cache: {total} total | {reclaimable} reclaimable | {reuse:.1f}% reused "
        "| {in_use} in use | {shared} shared"
    )
    build_cache_pruned: str = "Pruned BuildKit cache. Space reclaimed: {reclaimed}"


@dataclass(frozen=True)
class GrafanaMessages:
    url_not_configured: str = "Grafana URL not configured. Run: devops config set grafana.url <url>"
    table_title_lint: str = "Dashboard Lint Findings"
    no_dashboards_found: str = "No dashboard JSON files found under '{path}'."
    lint_summary: str = (
        "Linted {dashboards} dashboard(s), {panels} panel(s): {errors} error(s), "
        "{warnings} warning(s)."
    )
    table_title_dashboards: str = "Grafana Dashboards"
    exported_success: str = "Exported → {dest}"
    imported_success: str = "Imported: {slug}"
    dir_not_found: str = "Dashboard directory '{path}' not found."
    no_json_files: str = "No dashboard JSON files found in '{path}'."
    synced_dashboard: str = "Synced dashboard: [bold]{title}[/bold] ({file})"
    sync_skipped_provisioned: str = (
        "Skipped dashboard: [bold]{title}[/bold] ({file}) is provisioned from a file, and "
        "Grafana refuses API saves over it."
    )
    sync_completed: str = (
        "Dashboard sync completed: {synced} synced, {skipped} skipped, {failed} failed."
    )
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
    no_description_provided: str = "No description provided."


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
class BadgeMessages:
    active: str = "Active"
    disabled: str = "Disabled"
    verified: str = "✓ VERIFIED"
    mitigated: str = "~ MITIGATED"
    flagged: str = "FLAGGED"
    invalidated: str = "INVALIDATED"
    unverified: str = "? UNVERIFIED"
    sev_critical: str = "CRITICAL"
    sev_high: str = "HIGH"
    sev_medium: str = "MEDIUM"
    sev_low: str = "LOW"
    sev_info: str = "INFO"
    overdue_deletion: str = "overdue for deletion"
    grace_period: str = "grace period"
    rotation_soon: str = "rotation soon"


@dataclass(frozen=True)
class OutputMessages:
    finding_header: str = "Finding #{index}: [{sev}] {title}"
    location_label: str = "Location:"
    description_label: str = "Description:"
    suggested_fix_label: str = "Suggested Fix:"
    references_label: str = "References: {refs}"
    argo_sync_label: str = "Sync:"
    argo_health_label: str = "Health:"
    argo_revision_label: str = "Revision:"
    argo_error_fetching: str = "Error fetching status: {error}"


@dataclass(frozen=True)
class RoadmapMessages:
    epic_closed: str = (
        "Closed as not planned: a release is its milestone, so release epics are retired. "
        "GitHub issues, milestones and the project board are now the roadmap's source of "
        "truth (ADR 0001: {adr})."
    )
    not_planned_closed: str = (
        "Closed as not planned: the hand-written roadmap recorded it as {status} "
        "({location}). It stays on record so intake recognizes the idea as a duplicate if it "
        "surfaces again (ADR 0001: {adr})."
    )
    not_planned_body: str = (
        "The hand-written roadmap recorded this as not planned before GitHub became the "
        "roadmap's source of truth. Its text, from {location}:\n\n{text}"
    )
    report_title: str = "# Roadmap migration plan for {repo} at {ref}"
    report_p0: str = "## 1. P0 feature candidates for a later release"
    report_unfiled: str = "## 2. Open entries without an issue"
    report_closed: str = "## 3. Open entries whose issue is closed"
    report_writes: str = "## 4. Planned writes"
    report_left_alone: str = "### Left alone: set on the board and different from the matrix"
    report_auto_add: str = (
        "### Enabled auto-add workflows: turn these off in the board's Workflows page"
    )
    report_option_edits: str = (
        "### Option edits a person makes in the board's field settings, which keep option ids"
    )
    report_none: str = "None."
    report_not_imported: str = (
        "{path} carries the `devops roadmap render` marker, so it is a generated view and was "
        "not imported."
    )
    default_branch: str = "the default branch"
    board_created: str = (
        "Created board #{number} ({url}). Its Status options were replaced, so check the Status "
        "each built-in workflow sets in its Workflows page. Set `board = {number}` in {config}, "
        "then run migrate again."
    )
    applied: str = "Made {count} planned write(s)."
    nothing_to_do: str = "Nothing to migrate: GitHub already holds the roadmap."
    nothing_to_write: str = (
        "Nothing for migrate to write. Make the option edits listed above in the board's field "
        "settings."
    )
    edits_due: str = (
        "Make these option edits in the board's field settings first, because the planned "
        "writes set those options: {edits}. GitHub's API can't keep an option's id, so migrate "
        "never edits options itself."
    )
    preview_only: str = "Nothing was written. Run again with --confirm to make these writes."
    render_written: str = "Wrote {path}: {items} item(s) in {sections} section(s)."
    graphql_budget_refused: str = (
        "GraphQL has {remaining} points left until {reset}, and reading {what} costs about "
        "{cost} with {floor} kept in reserve, so the run stopped before reading and spent "
        "nothing on it. Run it again after {reset}."
    )
    graphql_budget_floor: str = (
        "GraphQL has {remaining} points left until {reset}, below the {floor} kept in reserve, "
        "so the read of {what} stopped before page {page}. Run it again after {reset}."
    )
    graphql_budget_write_floor: str = (
        "GraphQL has {remaining} points left until {reset}, below the {floor} kept in reserve, "
        "so the run stopped before writing {what}. Run it again after {reset}."
    )
    card_changed: str = (
        "{card}'s {field} is {now} on the board but was {read} when this run read it, so "
        "someone changed it since and the run stopped before writing it. Nothing was written; "
        "the next run reads the board again and plans with that change."
    )
    card_value_unset: str = "unset"
    board_count_changed: str = (
        "The {what} changed while they were read ({counts}), and again on a second read, so "
        "the read is incomplete. Run it again once the board is still."
    )
    board_items: str = "board #{number} items"
    board_items_filtered: str = 'board #{number} items matching "{query}"'
    board_reread: str = "The {what} changed while they were read ({counts}); reading them again."
    graphql_spend: str = "GraphQL: {spent} points spent, {remaining} left until {reset}."
    graphql_spend_since_reset: str = (
        "GraphQL: {spent} points spent since the hourly reset during the run, {remaining} left "
        "until {reset}."
    )
    render_current: str = "## Current release: {title}"
    render_planned: str = "## Planned release: {title}"
    render_backlog: str = "## Backlog"
    render_empty: str = "No items."
    # `devops roadmap reprioritize` (#740). Each reason completes its action's comment, and the
    # placeholders are {release}, {next}, {cap}, {days} and {detail}.
    reasons: dict[str, str] = field(
        default_factory=lambda: {
            "critical_fix": "a critical fix can join {release} after it starts.",
            "pull_request": "an open or merged pull request is in flight for it.",
            "admission": (
                "after {release} started, only a critical fix can join it. A person can place "
                "it in a planned release, and that placement stands."
            ),
            "p0_feature": (
                "a P0 feature waits for the next release once {release} has started, and goes "
                "first when {next} starts."
            ),
            "cut": (
                "{release} is cut, so nothing joins it until its release pull request is "
                "closed; a critical fix goes first into the next release."
            ),
            "cap": (
                "critical fix {detail} took {release} over its size of {cap} items, and this "
                "was its lowest-ranked unstarted item."
            ),
            "over_size": (
                "{release} holds {detail} items, more than its size of {cap} and more than it "
                "held when it started, and this was its lowest-ranked unstarted item."
            ),
            "blocked": "it is Blocked and had not started.",
            "dependency": "it waits on {detail}, open outside {release}.",
            "needs_split": "it is labeled needs-split, so it must be split before it fits one "
            "pull request.",
            "others_done": "every other item in {release} is done, and it had not started.",
            "fix_stays": "an admitted critical fix leaves {release} only when it is Blocked.",
            "stalled": (
                "it had no status change, pull request update or commit for {days} days, so it "
                "counts as not started again."
            ),
            "fix_stalled": (
                "it had no status change, pull request update or commit for {days} days; as a "
                "critical fix it stays in {release}."
            ),
            "review_idle": (
                "this item has been in review for {days} days without a status change, pull "
                "request update or commit, and it holds the cut of {release}."
            ),
            "shipped": (
                "{release} shipped: its release pull request merged and GitHub Release "
                "{release} is published."
            ),
            "not_ready_at_start": "it was New, not Ready, when {release} started.",
            "fix_new_at_start": "a New critical fix stays in a starting release.",
            "blocked_at_start": "a Blocked item can't join a starting release ({release}).",
            "top_up": (
                "{release} started with fewer than its {cap} items and was topped up to "
                "{detail} from Ready items, critical fixes and P0 features first."
            ),
            "trim": (
                "{release} started with more than {cap} items, and this was its lowest-ranked "
                "unstarted item."
            ),
        }
    )
    # What each action did, in the item's one-line comment; {reason} is one of `reasons`.
    actions: dict[str, str] = field(
        default_factory=lambda: {
            "keep": "Kept in {release}: {reason}",
            "admit": "Admitted to {release}: {reason}",
            "to_backlog": "Moved to the backlog: {reason}",
            "to_next": "Moved to {target}: {reason}",
            "ready": "Status set to Ready: {reason}",
            "ready_to_next": "Status set to Ready and moved to {target}: {reason}",
            "nudge": "Nudge: {reason}",
            "pull_in": "Moved to {target}: {reason}",
            "start_next": "{reason}",
        }
    )
    reprioritize_comment: str = "{text} (devops roadmap reprioritize)"
    reprioritize_title: str = "# Reprioritization of {repo}"
    reprioritize_current: str = "Current release: {release} ({state})."
    reprioritize_no_release: str = "No Release is open, so there is no current release."
    reprioritize_first_run: str = (
        "First run: the board has no run record yet, so this run records the admitted set of "
        "{release} and moves nothing. The rules apply to changes made after it."
    )
    reprioritize_first_run_at_ship: str = (
        "First run: the board has no run record yet, and {shipped} has shipped, so {release} "
        "is under way. This run records the admitted set of {release}, closes every shipped "
        "milestone still open and moves nothing. The rules apply to changes made after it."
    )
    reprioritize_unshipped: str = (
        "{release} is closed but has not shipped: its release pull request has not merged, or "
        "GitHub Release {release} is not published. {current} starts only once {release} "
        "ships, so this run starts nothing. Reopen {release} if it was closed by mistake."
    )
    reprioritize_unmigrated: str = (
        "#739's migration has not finished on this board: {problems}. Run `devops roadmap "
        "migrate` first, then reprioritize."
    )
    reprioritize_unmigrated_missing: str = "its Status field has no {found} option"
    reprioritize_unmigrated_merged: str = (
        "its Status field still has {found}, which migrate merges into New"
    )
    reprioritize_unmigrated_epics: str = "release epics {found} are still open on it"
    reprioritize_no_run_record: str = (
        'The board has no "{card}" draft card, yet {count} item(s) carry this job\'s marks '
        "({items}), so the job has run before: the card was deleted, archived, converted to "
        'an issue or renamed. Put it back as a draft issue titled "{card}", unarchived. A first '
        "run now would admit everything added to the current release since it started."
    )
    reprioritize_record_unreadable: str = (
        'The "{card}" card is on the board, but its run record can\'t be read: its Started '
        "mark is {started}, not a milestone number, so an older version of the job wrote it or "
        "it was edited by hand. Set the Started mark in its Job record to the milestone number "
        "of the release the job last started, as text: for the current release, {release}, "
        'that is "{number}". Then run the job again.'
    )
    reprioritize_record_gone: str = (
        'The "{card}" card names milestone #{number} as the release the job last started, and '
        "the repository has no such milestone. Restore it, or set the card's Started mark to "
        "the milestone number of the release under way."
    )
    reprioritize_behind: str = (
        "{current} is older than {started}, the release the run record names as started, so "
        "{current} never started and has no admitted set. This run holds no release to its "
        "rules and moves nothing until {current} ships or is closed."
    )
    reprioritize_start: str = "{shipped} shipped, so {starting} starts."
    reprioritize_start_after_close: str = (
        "{starting} starts: the release the run record names is closed."
    )
    reprioritize_changes: str = "## Changes"
    reprioritize_release_writes: str = "## Releases and branches"
    reprioritize_records: str = "## Admitted set"
    reprioritize_admits: str = "- {release} admits {items}."
    reprioritize_cleared: str = (
        "- {items} left {release} after it admitted them: their admitted marks are cleared, "
        "and a return to {release} is judged again."
    )
    reprioritize_left: str = (
        "- #{number} left {release}, where a job placed it, so a return to {release} is judged "
        "again."
    )
    reprioritize_left_backlog: str = (
        "- #{number} left the backlog, where a job placed it, so where a person puts it stands."
    )
    refine_ready_comment: str = "Status set to Ready at {sha} (see proposed design in issue body)."
    refine_split_comment: str = (
        "Proposal needs splitting into {count} items at {sha} (see proposed design in issue body)."
    )
    refine_title: str = "# Refinement plan for {repo}"
    refine_none: str = "No items to refine."
    reprioritize_kept_out: str = (
        "- #{number} was taken out of {release} by a person, as its issue's events show, so it "
        "stays in the backlog: a person's placement stands."
    )
    reprioritize_change_line: str = "- #{number} {title}: {text}"
    reprioritize_resumed_line: str = (
        "- #{number} {title}: {text} (finishing what an earlier run began)"
    )
    reprioritize_dropped_line: str = (
        "- #{number} {title}: not finishing what an earlier run began ({text}): a person has "
        "changed the item since, or the rules no longer decide it, so what that run wrote is "
        "put back."
    )
    reprioritize_unreadable_line: str = (
        "- #{number} {title}: an earlier run left a change this run can't read, or one about a "
        "release that is gone, so it is dropped."
    )
    reprioritize_run_record: str = (
        "- The run record names {release}, holding {size} item(s), so the next run holds it "
        "to its rules."
    )
    reprioritize_nothing: str = "Nothing to do: the current release already keeps its rules."
    reprioritize_preview: str = (
        "Nothing was written. Run again with --confirm to make these changes."
    )
    reprioritize_applied: str = "Made {changes} change(s) and {records} job-record mark(s)."
    reprioritize_close_release: str = "close Release {release}"
    reprioritize_create_release: str = "create Release {release}"
    reprioritize_create_branch: str = "create branch {branch} at {sha}"
    # The dry runs of `devops roadmap` (#412, #1125): the requests a run makes, none made.
    plan_dry_run: str = (
        "Dry run: no request was made. A run makes these requests, in order; a value in "
        "<angle brackets> comes from an earlier read, a step with a condition runs only when it "
        "holds, and a step repeated runs as often as it says."
    )
    plan_dry_run_writes: str = "With --confirm, after the reads and before the last request:"
    plan_dry_run_title: str = "# devops roadmap {job} for {repo}"
    plan_dry_run_render: str = "Then render writes {path}, which makes no request."
    plan_dry_run_notes: tuple[str, ...] = (
        "A board read whose count changes while it is read reads it once more, from its first "
        "page. run_gh may read `gh api rate_limit` to pace a request; that read costs no quota.",
    )
    plan_modes_exclusive: str = "Pass one of {modes}, not more."
    plan_repeat_page: str = "per page, until a page is short"
    plan_repeat_board_page: str = "per page after the first, while GraphQL reports a next page"
    plan_placeholders: dict[str, str] = field(
        default_factory=lambda: {
            "board": "<board>",
            "cursor": "<cursor>",
            "page": "<n>",
            "number": "<number>",
            "milestone": "<milestone>",
            "release": "<release>",
            "tag": "<tag>",
            "branch": "<branch>",
            "sha": "<sha>",
            "url": "<issue url>",
            "value": "<value>",
            "record": "<job record>",
            "board_id": "<board id>",
            "field_id": "<field id>",
            "card_id": "<card id>",
            "option_id": "<option id>",
            "comment": "<comment>",
            "title": "<title>",
            "body": "<body>",
            "label": "<label>",
            "node_id": "<node id>",
            "original_id": "<original node id>",
            "evidence": "<evidence>",
            "field": "<field>",
            "item": "<item>",
            "card": "<card>",
            "new_board": "<new board>",
            "since": "<since>",
        }
    )
    plan_targets: dict[str, str] = field(
        default_factory=lambda: {
            "file": "{path} at {ref}",
            "milestones": "every milestone",
            "issues": "the issues ({query})",
            "board_budget": (
                "GraphQL's points left and the total of board {board}'s items{matching}; the "
                "read stops here when the points can't cover it"
            ),
            "board_first": "the first page of board {board}'s items{matching}",
            "board_page": "the next page of board {board}'s items{matching}",
            "fields": "board {board}'s node id and fields, with their options",
            "card": (
                "the card of {subject}: its fields, its job record and GraphQL's points left; a "
                "write stops here when the points are below the reserve, or when someone changed "
                "the field it writes since the run read it"
            ),
            "workflows": "board {board}'s workflows",
            "boards": "{owner}'s boards, to find board {board}",
            "default_branch": "the default branch and its head",
            "release_prs": "the release pull requests of {release}",
            "release_published": "GitHub Release {release}",
            "open_prs": "every open pull request",
            "status_at": "when the Status of {subject} last changed",
            "events": "the events of {subject}",
            "comments": "the comments on {subject}",
            "dependencies": "the issues {subject} is blocked by",
            "branch": "branch {branch}",
            "issue": "{subject}",
            "issue_events": "the repository's issue events since {since}",
            "count": "count the issues matching {query}",
            "closures": "the closes and reopens on {subject}'s timeline",
            "advisory": "the advisory {subject} cites",
            "workflow_run": "the workflow run {subject} cites",
            "commit": "the commit {subject} cites",
            "create_release": "create Release {release}",
            "edit_release": "close Release {release}",
            "delete_release": "delete Release {release}",
            "create_branch": "create branch {branch} at {sha}",
            "record": "the job record of {subject}",
            "set_field": "set {field} on {subject}",
            "milestone": "set the milestone of {subject}",
            "comment": "comment on {subject}",
            "label": "label {subject}",
            "add_item": "add {subject} to board {board}",
            "close_issue": "close {subject}",
            "close_duplicate": "close {subject} as a duplicate",
            "create_issue": "open an issue for {subject}",
            "create_card": "create the run record card",
            "run_record": "the run record",
            "card_field": "set {field} on {subject}",
            "remove_card": "remove {subject} from board {board}",
            "create_board": "create the board",
            "link_board": "link the new board to the repository",
            "create_field": "create or align a template field on the new board",
            "delete_field": "delete the {field} field",
            "budget": "GraphQL's points spent and left, for the run's last line",
            "merged_prs": "the pull requests merged into {branch}",
            "pr_files": "the files pull request {subject} changed",
            "pr_checks": "the check runs of pull request {subject}",
            "milestone_issues": "the issues in milestone {release}, for the pull request body",
            "milestone_prs": "the pull requests in milestone {release}, for the pull request body",
            "pr_create": "open the release pull request from {branch}",
            "git_fetch": "fetch {branch} from origin into the clone",
            "git_push": "push {branch} to origin, replacing an earlier cut",
        }
    )
    plan_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "pending": "an item holds a change an earlier run began",
            "current": "a release is current",
            "merged": "a release pull request merged",
            "judged": "the run judges an item it needs this for",
            "starting": "the run starts the next release",
            "change": "the run changes an item",
            "release_field": "the change sets the Release",
            "other_field": "the change sets a field other than the Release",
            "posted": "the change posts a comment",
            "record": "the run records its release or size",
            "no_card": "the board has no run record card yet",
            "run_card": "the board has the run record card",
            "board_unread": (
                "the run has not read these items of the board since it began or last closed an "
                "issue"
            ),
            "fields_unread": "the run has not read the board's fields yet",
            "closing": "a shipped release's milestone is still open",
            "release_named": "the value is a Release",
            "board": "the configured board exists",
            "no_board": "there is no board yet",
            "renamed": "the board has a field the template drops",
            "card": "the run sets a field on a card",
            "epic": "the board holds a release epic",
            "beyond": "a release lies beyond the planning horizon",
            "unset": "an item has the field unset",
            "not_planned": "the roadmap lists a rejected idea",
            "unfiled": "the rejected idea has no issue",
            "done": "the run is done: it comes after any write",
            "closes": "a merged pull request closes an open issue",
            "task_file": "the pull request changed a task file of the issue",
            "no_open": "the release holds no open item",
            "cut": "the release is due to be cut",
        }
    )
    plan_repeat: dict[str, str] = field(
        default_factory=lambda: {
            "release": "for the current release and each planned one in the horizon",
            "pending": "for each such item",
            "item": "for each item the run judges or changes",
            "write": "for each such write",
            "evidence": "for each piece of evidence the model cites",
            "field": "for each template field",
            "merged": "for each merged pull request",
            "closing": "for each issue the run closes",
            "completed": "for each item closed as completed",
        }
    )
    # `devops roadmap close` (#743).
    close_title: str = "# Closure for {repo}, release {release}"
    close_closing: str = "Close #{number} as completed (delivered by #{pull_request}), commenting:"
    close_nothing: str = "No open issue to close."
    close_unread: str = (
        "Pull request #{number} closes {issues}, which stay open: its check runs could not be "
        "read ({reason}). The next run retries."
    )
    close_holds: dict[str, str] = field(
        default_factory=lambda: {
            "no_release": "No cut: there is no open Release.",
            "unread": "No cut for {release}: a pull request's check runs could not be read.",
            "open_items": "No cut for {release}: these items are still open:",
            "nothing_delivered": (
                "No cut for {release}: no item in it was closed as completed, so it delivers "
                "nothing."
            ),
            "pr_open": "No cut for {release}: its release pull request #{number} is open.",
            "pr_merged": (
                "No cut for {release}: its release pull request #{number} has merged, so it "
                "has shipped."
            ),
        }
    )
    close_open_item: str = "- #{number} {title}"
    close_cut: str = "Cut: push {branch} and open the release pull request into {base}, '{title}'."
    close_cut_files: str = "The cut commit changes {files}."
    close_cut_fragments: str = (
        "Changelog fragments on the release branch, left uncollected: {fragments}."
    )
    close_cut_missing: str = (
        "Closed as completed with no changelog fragment (a person adds it on the release pull "
        "request): {items}."
    )
    close_none: str = "none"
    close_dry_run_note: str = (
        "A cut commits {files} on release/<release> and opens it ready for review. --plan "
        "reads GitHub and lists each issue the run closes with its comment, the fragments on "
        "the release branch, left uncollected, and the completed items with none."
    )
    close_preview: str = "Nothing was written; pass --confirm to close these and make the cut."
    close_applied: str = "Closed {count} issue(s)."
    close_failed: str = "Closure is incomplete: {count} pull request(s) had unreadable check runs."
    close_criteria_heading: str = "Acceptance Criteria"
    close_comment_changed: str = "### What changed"
    close_comment_merged: str = "{url}, merged into `{branch}` as {commit}."
    close_comment_files: str = "{count} file(s) changed."
    close_comment_verified: str = "### How it was verified"
    close_comment_checks: str = "Check runs at {commit}:"
    close_comment_check: str = "- {name}: {bucket}"
    close_comment_no_checks: str = "No check runs."
    close_comment_task: str = "Acceptance Criteria of `{path}`:"
    close_comment_no_criteria: str = "No Acceptance Criteria section."
    close_comment_no_task: str = "No task file."
    # `devops roadmap intake` (#742).
    intake_title: str = "# Intake for {repo}"
    intake_quota: str = (
        "Quota (#1153): {open} open issues, r(n) = {ratio:.2f}; credit {credit} from "
        "{delivered} delivered by {previous}; {closures} closure(s) since {since}; allowance "
        "{allowance}; {openings} agent opening(s) this cycle, {borrowed} borrowed."
    )
    intake_no_previous: str = "no closed release"
    intake_since_ever: str = "the repository began"
    intake_unlimited: str = "no limit"
    intake_nothing: str = "No candidates and no unfinished items."
    intake_issue: str = "#{number} {title}"
    intake_new: str = 'new candidate "{title}"'
    intake_not_candidate: str = (
        "- #{number}: neither an open issue off the board nor an unfinished item, so intake "
        "leaves it alone."
    )
    intake_place_line: str = (
        "- {subject}: {type}, {priority}, Value {value}, Effort {effort}; {placement} "
        "Quota: {quota}."
    )
    intake_duplicate_line: str = "- {subject}: duplicate of #{original}: {reason} {action}"
    intake_duplicate_closes: str = "It is closed as a duplicate."
    intake_duplicate_files_nothing: str = "Nothing is filed; add to #{original} instead."
    intake_fold_line: str = (
        "- {subject}: fold into {target}: the cycle's allowance of {allowance} agent opening(s) "
        "is used, and it is not a split, a required follow-up or a P0/P1 bug or security "
        "issue. Nothing is filed; add it to that item as an amendment or a comment."
    )
    intake_fold_open: str = (
        "- {subject}: fold into {target}: this cycle's agent openings are past the allowance of "
        "{allowance}, and it is not a P0/P1 bug or security issue. Intake leaves it off the "
        "board; add it to that item as an amendment or a comment, and close it."
    )
    intake_fold_nowhere: str = "an existing item"
    intake_quota_fold: str = "Quota: fold into #{target}."
    intake_quota_suffix: str = "Quota: {quota}."
    intake_skip_line: str = "- {subject}: skipped, nothing written: {reason}"
    intake_writes: str = "  - writes: {writes}"
    intake_note: str = "  - note: {note}"
    intake_write_file: str = "file the issue with {labels}"
    intake_no_labels: str = "no labels"
    intake_write_label: str = "label {label}"
    intake_write_add: str = "add to the board"
    intake_write_release: str = "milestone {release}"
    intake_write_backlog: str = "clear the milestone"
    intake_write_field: str = "{field} {value}"
    intake_write_comment: str = "reason comment"
    intake_write_close: str = "comment and close as a duplicate of #{original}"
    intake_write_close_only: str = "close as a duplicate of #{original} (its comment is there)"
    intake_placement_backlog: str = "to the backlog: {reason}"
    intake_placement_release: str = "to {release}: {reason}"
    intake_placement_kept: str = "kept in {release}: {reason}"
    intake_reason_backlog: str = (
        "at intake only a critical fix goes into a release; a release start pulls Ready items "
        "in, P0 features first."
    )
    intake_reason_person: str = "a person placed it in {release}, and that placement stands."
    intake_reason_current_not_critical: str = (
        "only a critical fix joins the current release at intake; a release start pulls Ready "
        "items in, P0 features first."
    )
    intake_reason_resumed: str = "it was already in {release}."
    intake_reason_no_release: str = "no Release is open, so a critical fix waits in the backlog."
    intake_reason_no_next: str = (
        "{release} admits no more, and no planned release follows it, so it waits in the backlog."
    )
    intake_comment: str = "{marker}\nIntake placed this item {placement}\n\n{fields}"
    intake_comment_field: str = "- {field}: {value}. {reason}"
    intake_duplicate_comment: str = (
        "{marker}\nClosed as a duplicate of #{original}: {reason}\n\nIf it is not a duplicate, "
        "reopen it: intake then places it without the duplicate check."
    )
    intake_p0_granted: str = (
        "P0: the {kind} {value} is evidence GitHub confirms, from a trusted source."
    )
    intake_p0_refused: str = (
        "The {kind} {value} does not set P0: {why}. A person can set P0 on the board."
    )
    intake_why_not_verbatim: str = "it does not appear in the candidate's text"
    intake_why_untrusted: str = (
        "the author has no write access, and no caller attached it as evidence"
    )
    intake_why_unconfirmed: dict[str, str] = field(
        default_factory=lambda: {
            "advisory": "GitHub has no such advisory",
            "failed_run": "no failed run of this repository has that id",
            "regression_commit": "this repository has no such commit",
        }
    )
    intake_note_duplicate_rejected: str = (
        "the model named #{number} as the original, which is not one of the nearest items, so "
        "it was rejected."
    )
    intake_note_priority_capped: str = (
        "the model proposed {priority}, and it can propose only P1 to P3, so {capped} stands."
    )
    intake_note_evidence_dropped: str = (
        "the model's evidence ({kind} {value}) is not a GHSA ID, a run id or a commit SHA, so it "
        "was dropped."
    )
    intake_note_borrow_judged: str = (
        "it borrows as a {priority} {type}, which rests on the model's judgement, not a person's "
        "or verified evidence; a person can remove {label}."
    )
    intake_invalid: str = "the model's proposal is not valid: {problems}"
    intake_invalid_value: str = "{field} {value!r} is not one of {choices}"
    intake_quota_decisions: dict[str, str] = field(
        default_factory=lambda: {
            "open": "open, within the allowance",
            "borrow": "borrowed beyond the allowance (budget/borrowed)",
            "fold": "fold",
            "not_counted": "not counted (no source/agent label)",
        }
    )
    intake_preview: str = "Nothing was written. Run again with --confirm to make these writes."
    intake_plain_note: str = (
        "Intake without a mode flag runs as --plan: it reads GitHub and calls the model, and "
        "writes nothing. --dry-run makes no request."
    )
    intake_spend: str = (
        "Spent: {github} GitHub request(s) (REST {rest}, REST search {search}, GraphQL "
        "{graphql}; GraphQL points not known), {embeddings} embedding call(s) for {texts} "
        "text(s), {proposals} proposal call(s)."
    )
    intake_dry_run: str = (
        "Dry run: no request was made. A run makes these requests, in order; a value in "
        "<angle brackets> comes from an earlier read, and a step with a condition runs only "
        "when it holds."
    )
    intake_dry_run_writes: str = (
        "With --confirm, after the reads and before the last request, for each candidate "
        "intake places or closes as a duplicate:"
    )
    intake_request_read: str = "read"
    intake_request_write: str = "write"
    intake_repeat_page: str = "per page, until a page is short"
    intake_repeat_candidate: str = (
        "for each candidate: an open issue off the board or an item without a Priority"
    )
    intake_placeholder_default_branch: str = "the default branch"
    intake_placeholder_board: str = "<the board .github/roadmap.toml names>"
    intake_placeholder_since: str = "<the previous release's close>"
    intake_placeholder_each: str = "<the candidate>"
    intake_placeholder_filed: str = "<the filed issue>"
    intake_placeholder_fields: tuple[str, ...] = (
        "Status New",
        "Value <the proposed Value>",
        "Effort <the proposed Effort>",
    )
    intake_requests: dict[str, str] = field(
        default_factory=lambda: {
            "config": ".github/roadmap.toml at {ref}, which names the board",
            "milestones": "every milestone",
            "issues": "every issue, open and closed",
            "board": "the items on board {board}, a page of GraphQL at a time",
            "board_issues": "every issue again, to join the board's items",
            "quota_milestones": "every milestone again, for the quota's cycle",
            "count_open": "count the open issues",
            "count_closed": "count the issues closed since {since}",
            "count_bulk": "count the issues closed as not planned with no comment since {since}",
            "count_openings": "count the source/agent issues created since {since}",
            "count_borrowed": (
                "count the source/agent issues labeled budget/borrowed created since {since}"
            ),
            "closures": "the closes and reopens on {subject}'s timeline",
            "embed": (
                "every item, every issue closed as not planned and each candidate off the "
                "board, in one call"
            ),
            "embed_new": (
                "every item, every issue closed as not planned, the open source/agent issues "
                "off the board and the new candidate, in one call"
            ),
            "labels": ".github/labels.yml at {ref}, for the type/* labels, once",
            "propose": "the proposal for {subject}",
            "evidence": "the evidence the model cites for {subject}",
            "default_branch": "the default branch",
            "release_milestones": "every milestone again, to find <the current release>",
            "release_prs": "the release pull requests of <the current release>",
            "release_published": "GitHub Release <the current release>",
            "comments": "the comments on {subject}, for intake's marker",
            "file": ("file {subject} with source/agent, and budget/borrowed when it borrows"),
            "label": (
                "label {subject} with its type/* label when it has none, and budget/borrowed "
                "when it borrows"
            ),
            "add": "read {subject}, add it to board {board}, then read the card the add names",
            "release": (
                "set the milestone of {subject} to <the placement>: the board's fields once a "
                "run, every milestone, its card, the job record (GraphQL), then the milestone "
                "(REST)"
            ),
            "field": (
                "set {field} on {subject}: the board's fields once a run, its card, the job "
                "record, then the field"
            ),
            "comment": "the reason comment on {subject}",
            "priority": (
                "set Priority <the proposed Priority> on {subject}: the board's fields once a "
                "run, its card, the job record, then the field"
            ),
            "duplicate_read": "{subject} and <the original>",
            "duplicate_comment": "the duplicate comment on {subject}",
            "duplicate_close": "close {subject} as a duplicate of <the original>",
        }
    )
    intake_request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "closures": "{subject} is not on the board",
            "embed": "a candidate is off the board",
            "evidence": "the model cites any",
            "release_state": "it is the first critical fix of the run while a release is current",
            "release_published": "one of them merged",
            "comments": "{subject} is placed or a duplicate",
            "file": "it is not a duplicate and does not fold",
            "placed": "intake places {subject}",
            "add": "it is not on the board",
            "release": "the placement changes it",
            "field": "it has none",
            "comment": "intake's is not there",
            "duplicate": "{subject} is a duplicate instead of placed",
            "duplicate_comment": "intake's is not there",
        }
    )
    intake_applied: str = "Intake placed {placed} item(s) and closed {closed} duplicate(s)."
    intake_filed: str = "Filed #{number}."
    triage_no_board: str = (
        "This repository has no .github/roadmap.toml, so issues awaiting intake are not reported."
    )
    triage_awaiting_intake: str = (
        "Issues awaiting intake get their type and Priority from `devops roadmap intake`."
    )
    intake_title_needs_body: str = "Pass --title and --body-file together."
    intake_borrow_needs_source: str = (
        "--borrow-reason needs --source: the link to the item it splits from, or to the review "
        "that requires the follow-up."
    )
    intake_secret: str = (
        "The candidate's {part} holds what looks like a secret, so intake sent it to no model "
        "and filed nothing. Remove it and run again."
    )
    intake_borrow_needs_title: str = (
        "--borrow-reason applies to a new candidate; pass it with --title and --body-file."
    )
    intake_issue_or_title: str = (
        "Pass --issue for existing issues, or --title and --body-file for a new candidate, "
        "not both."
    )


@dataclass(frozen=True)
class ProjectMessages:
    """`devops gh project sync` and `devops gh project reconcile` (#892)."""

    budget_read: str = "the GraphQL budget for reading {what}"
    no_status_options: str = (
        "Project #{number} has no Status field with options, so reconcile can't tell which "
        "status/* labels it may set. Create the field with `devops gh project sync`."
    )
    changes_title: str = "Project #{number} Field Changes"
    summary_plan: str = (
        "Would change {items} of {evaluated} items on project #{number} ({changes} field changes)."
    )
    summary_write: str = (
        "Changed {items} of {evaluated} items on project #{number} ({changes} field changes)."
    )
    stopped: str = "Stopped early ({reason}): {remaining}."
    # Indexed by whether the count is other than one.
    remaining: tuple[str, str] = (
        "{count} planned change remains",
        "{count} planned changes remain",
    )
    stop_budget: str = "mutation budget of {limit} reached"
    stop_quota: str = (
        "GraphQL has {remaining} points left until {reset}, below the {floor} kept in reserve"
    )
    stop_write_failed: str = "the write of {field} on {item} failed: {error}"
    awaiting_intake: tuple[str, str] = (
        "{count} open issue is not on the board (awaiting intake: devops roadmap intake).",
        "{count} open issues are not on the board (awaiting intake: devops roadmap intake).",
    )
    dry_run_title: str = "# devops gh project reconcile for {repo}"
    dry_run_notes: tuple[str, ...] = (
        "run_gh may read `gh api rate_limit` to pace a request; that read costs no quota.",
    )
    request_placeholders: dict[str, str] = field(
        default_factory=lambda: {
            "board": "<board>",
            "login": "<login>",
            "cursor": "<cursor>",
            "url": "<item url>",
            "field": "<field>",
            "value": "<value>",
            "owner_arg": "<{owner} or @me>",
        }
    )
    request_targets: dict[str, str] = field(
        default_factory=lambda: {
            "repo_boards": "the boards linked to {repo}, {found}",
            "owner_boards": "{owner}'s boards, {found}",
            "project_list": "{owner}'s boards through gh project list, {found}",
            "find": "to find the board named '{name}'",
            "login": "the signed-in login",
            "budget": (
                "GraphQL's points left and the total of board {board}'s items; the run stops here "
                "when the points can't cover the read"
            ),
            "first": "the first page of board {board}'s items",
            "page": "the next page of board {board}'s items",
            "fields": "board {board}'s fields, for the options a change may set",
            "issues": "the issues of {repo} in state {state}, every page",
            "pulls": "the pull requests of {repo} in state {state}, every page",
            "edit": "set a planned field change on a card of board {board}",
        }
    )
    request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "not_found": "no board named {names} was found",
            "login_unread": ", and the login was not read earlier in the run",
        }
    )
    request_repeat_edit: str = (
        "for each planned change, in order, until {limit} are made, GraphQL keeps fewer than "
        "{floor} points, or a write fails"
    )
    request_repeat_owner_fallback: str = (
        "once more with --owner @me when GitHub answers 'unknown owner type'"
    )
    sync_done: str = "Project '{title}' (#{number}){linked}. Provisioned fields: {fields}."
    sync_linked: str = " linked to {repo}"
    sync_fields_current: str = "all up-to-date"
    sync_dry_run: str = (
        "[DRY RUN] No request was made. A sync finds board '{title}' of {owner}, or creates it, "
        "links it to {repo}, creates the template fields it lacks ({fields}){reconcile}. It "
        "adds no issue or pull request to the board."
    )
    sync_dry_run_reconcile: str = ", and reconciles Status and Priority on the cards already on it"


@dataclass(frozen=True)
class LanguageCatalog:
    persona_titles: PersonaTitles = field(default_factory=PersonaTitles)
    messages: GeneralMessages = field(default_factory=GeneralMessages)
    badges: BadgeMessages = field(default_factory=BadgeMessages)
    output: OutputMessages = field(default_factory=OutputMessages)
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
    roadmap: RoadmapMessages = field(default_factory=RoadmapMessages)
    project: ProjectMessages = field(default_factory=ProjectMessages)


MESSAGES = LanguageCatalog()
