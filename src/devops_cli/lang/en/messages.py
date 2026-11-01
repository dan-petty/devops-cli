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
    session_start: str = (
        "Initializing review pipeline session '{session_id}' for {count} file(s) via {server}..."
    )
    session_start_without_model: str = (
        "Initializing review pipeline session '{session_id}' for {count} file(s) without a model..."
    )
    pre_analysis_summary: str = (
        "✓ Pre-analysis metadata for {count} file(s): {analyzed} analyzed, {reused} reused from "
        "the cache"
    )
    generating_metadata: str = "Generating segment metadata..."
    stage_metadata: str = "Analyzing metadata across {count} file(s)..."
    stage_segment: str = "Reviewing {count} file(s)..."
    stage_compose: str = "Composing final review..."
    gateway_concurrency_clamped: str = (
        "--concurrency {requested} is above the gateway's {slots} backend slots; using {slots}"
    )
    segment_progress: str = "  ✓ segment {index}/{total} in {elapsed}"
    segment_progress_dryrun: str = "  ✓ segment {index}/{total} (dry-run)"
    total_elapsed: str = "  total {elapsed}"
    collecting_files: str = "Collecting {pattern} files under {target}..."
    no_files_found: str = "No files found."
    no_reviewable_files_changed: str = "No reviewable files changed."
    diffing_branches: str = "Diffing {branch} against {base}..."
    no_diff_found: str = "No differences found between branches."
    nothing_for_personas: str = (
        "Nothing is left for the personas: every file under review is a lockfile, a planning "
        "document or a generated reference. The secret scan still reads {count} of them."
    )
    tools_not_sandboxed: str = (
        "The review tools did not run: {cause}. No tool runs outside the sandbox, so the report "
        "shows a coverage gap for each tool. To run the tools, install bubblewrap and util-linux "
        "on this host, or let bubblewrap make user namespaces (on Ubuntu, an AppArmor profile "
        "with the userns rule)."
    )
    nothing_for_personas_unscanned: str = (
        "Nothing is left for the personas: every file under review is a lockfile, a planning "
        "document or a generated reference. The static scan is off, so none of the {count} "
        "is read."
    )
    fetching_pr: str = "Fetching PR #{number} from {repo}..."
    findings_saved: str = "  ✓ findings saved → {path}"
    review_saved: str = "Review saved → {path}"
    session_not_kept: str = (
        "No review session is kept: the reporting stage is off, and it is the one that writes "
        "the findings a session is listed by."
    )
    code_changed_during_run: str = (
        "devops-cli's own source or prompts changed while this review ran, by a commit or an "
        "edit to its checkout. Later stages may have run different code or prompts than "
        "earlier stages. Run reviews from a checkout that stays put."
    )
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
    score_no_sessions: str = (
        "Name the SESSION directories to score, or write the golden set with --materialise-golden."
    )
    score_golden_takes_no_sessions: str = "--materialise-golden takes no SESSION directories."
    score_golden_written: str = (
        "Golden set written → [bold]{path}[/bold]: {files} files in commit {commit}. Review it "
        "with: devops review path {path}"
    )
    updated_finding_status: str = "Updated finding #{index} status → {status}"
    updated_candidate_status: str = "Updated candidate #{index} status → {status}"
    candidate_moved: str = "Candidate #{index} added to findings.json as finding #{number}"
    candidate_copy_ambiguous: str = (
        "Finding #{number} in findings.json reports candidates {candidates}, which share a "
        "persona, title, location and description; give the verdict there with --index {number}, "
        "which records it on each."
    )
    session_write_failed: str = (
        "Cannot write the session's files, so the verdict was not recorded: {error}"
    )
    suppressions_cover_changes: str = (
        "[bold yellow]{count} review.toml suppression(s) cover files this change touches; "
        "check that each reason still holds:[/bold yellow]"
    )
    suppression_covers_change: str = (
        "  • [cyan]{rule}[/cyan] on [cyan]{path}[/cyan] (expires {expiry}): {reason}"
    )
    suppression_never_expires: str = "never"
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
    rules_test_passed: str = (
        "Tested {count} rule(s) with Semgrep {version}; wrote [bold]{path}[/bold]."
    )
    rules_test_checked: str = (
        "Tested {count} rule(s) with Semgrep {version}; [bold]{path}[/bold] is up to date."
    )
    rules_fetch_dry_run_heading: str = (
        "Dry run: no request was made. rules fetch would make these requests, in order:"
    )
    rules_fetch_dry_run_writes: str = (
        "It would then write the ruleset to {rules} and its ETag to {etag}."
    )
    rules_fetch_cached: str = "Cached {count} rule(s) of {ruleset} in [bold]{path}[/bold]."
    rules_fetch_current: str = "The cached {ruleset} in [bold]{path}[/bold] is current."
    registry_ruleset_invalid: str = (
        "'{ruleset}' is not a Semgrep registry id. Write the kind ({kinds}), a slash and one name "
        "with no path, query or fragment in it, such as p/default."
    )
    registry_answer_refused: str = "the registry answered HTTP {status}"
    registry_answer_too_large: str = "the ruleset is larger than {limit} bytes"
    registry_answer_not_a_ruleset: str = (
        "The answer from {url} is not a Semgrep ruleset: it needs a `rules` list of at least one "
        "rule, each with an id."
    )
    registry_not_cached: str = (
        "The registry rules {ruleset} are not cached, or the cached file is not a Semgrep "
        "ruleset. Run `devops review rules fetch --ruleset {ruleset}`."
    )
    registry_cache_old: str = (
        "The cached registry rules {ruleset} are {hours} hours old, and the scan uses them. "
        "Run `devops review rules fetch --ruleset {ruleset}` to refresh them."
    )
    files_not_scanned: str = "Files not scanned: {count}. The Coverage section lists them."
    filed_findings_search_target: str = "issues that carry a review finding marker"
    filed_findings_search_repeat: str = "per page of 100 issues, while the search has more results"
    # Why a session is not on merged code (#2420), and the hand-off of its findings to intake.
    merged_reason_no_subject: str = "the session records no target"
    merged_reason_target: str = "the session reviewed a {type}, not a path"
    merged_reason_no_checkout: str = "the session records no checkout"
    merged_reason_dirty: str = "the working tree had a change when the review started"
    merged_reason_not_on_main: str = (
        "origin/main does not hold the commit {head}. If the commit is merged, run `git fetch "
        "origin` and try again"
    )
    hand_off_refused: str = (
        "Session {session} is not on merged code: {reason}. Only the findings of a path review "
        "of a clean tree at a commit on origin/main go to roadmap intake."
    )
    hand_off_hint: str = (
        "{count} findings of this session can go to roadmap intake when origin/main holds its "
        "commit. Run: devops review intake {session} --plan"
    )
    hand_off_none: str = "No finding of session {session} qualifies for roadmap intake."
    hand_off_all_filed: str = (
        "An issue already holds each of the {count} qualifying findings of session {session}. "
        "No finding is left to hand off."
    )
    hand_off_settled: str = "{count} qualifying findings are already in an issue and stay out."
    hand_off_secret: str = (
        "The candidate of the finding at {location} looks like it holds a secret, so the hand-off "
        "stopped before any request. Remove the secret from the finding, or suppress the finding."
    )
    hand_off_dry_run_candidates: str = (
        "The hand-off sends these {count} candidates to roadmap intake, in this order:"
    )
    hand_off_dry_run_note: str = (
        "Intake makes the requests after the issue search for each candidate in turn. The list "
        "shows them for the first candidate."
    )
    hand_off_plan_note: str = (
        "Nothing was written. Run with --confirm to file and place the candidates."
    )
    hand_off_skipped: str = (
        "Intake skipped {count} candidates, because the model's proposal was not usable."
    )
    hand_off_filed: str = "Intake filed #{number}."
    hand_off_no_checkout: str = (
        "Run `devops review intake` in the checkout that the session reviewed: the working "
        "directory is in no checkout."
    )
    hand_off_no_repo: str = (
        "Cannot find the repository from the origin of this checkout. Give it with --repo "
        "owner/name."
    )
    hand_off_body: str = (
        "## Problem Description\n\n"
        "A review of merged code found this with {tool}.\n\n"
        "{description}\n\n"
        "## Evidence\n\n"
        "- Session: `{session}`\n"
        "- Location: `{location}`\n"
        "- Tool: `{tool}`\n"
        "- Severity: {severity}\n"
        "- Verdict: {verdict}"
    )
    hand_off_cited_code: str = "## Cited Code"
    hand_off_fix: str = "## Proposed Fix"
    hand_off_criteria: str = "## Verification Criteria"


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
    agents_md_over_cap: str = (
        "The model wrote {chars} characters, more than the AGENTS.md cap of {cap}. "
        "The template router is written instead."
    )
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
    hosted_model_unpriced: str = (
        "genai-prices and the price overrides hold no price for model {model} under provider "
        "{provider}. Its requests are recorded at $0 with the pricing source unknown."
    )
    reference_model_unpriced: str = (
        "genai-prices and the price overrides hold no price for {model} ({setting}) under "
        "provider {provider}, so the local savings of {kind} tokens are unpriced."
    )
    savings_unpriced: str = "unpriced"
    payoff_unpriced: str = (
        "The hardware pay-off is not calculated: the local savings are unpriced, because "
        "genai-prices has no price for {models}."
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
    unknown_key: str = "Unknown config key: '{key}'"
    similar_keys: str = "Known keys with a similar name: {keys}"
    value_required: str = "{key} needs a VALUE; only a credential may be typed at a hidden prompt."
    secret_prompt: str = "{key} (typing hidden)"
    from_file_not_secret: str = (
        "{key} is not a credential. Only a credential comes from a file or stdin; give its VALUE."
    )
    from_file_and_value: str = "Give VALUE or --from-file, not both."
    from_file_oversize: str = "The input is larger than {limit} bytes, the limit for a credential."
    from_file_not_text: str = "The input is not UTF-8 text."
    from_file_empty: str = "The input holds no value."
    unset_success: str = "Removed {key} from {path}:{line}."
    unset_backup: str = "The file before the change is in {backup}."
    plaintext_alert: str = (
        "Security Alert: Found plaintext secrets stored in config files: {leaks}. "
        "Each entry reads <file>:<key>.\n"
        "To remove a leak, do these steps for each entry:\n"
        "1. Store a credential in the OS keyring: 'devops config set <key>'. "
        "For a multi-line credential, such as a PEM key, add '--from-file <path>'.\n"
        "2. Remove the plaintext value from its file: "
        "'DEVOPS_CLI_CONFIG=<file> devops config unset <key>'. "
        "Quote <file> and <key> for the shell.\n"
        "A key that is not a config option needs only step 2."
    )


@dataclass(frozen=True)
class InstallMessages:
    status_title: str = "DevOps Tool Status"
    checking_tools: str = "Checking DevOps toolchain versions..."
    installing_tool: str = "Installing [cyan]{name}[/cyan] {version}..."
    tool_installed: str = "✓ {name} {version} installed to {path}"
    tool_already_installed: str = "✓ {name} is already installed ({version})"
    download_failed: str = "Error downloading {name} from {url}: {exc}"
    at_pin: str = "at pin"
    not_installed: str = "not installed"
    check_off_pin: str = "{name} {version}: {installed}"
    check_all_pinned: str = "All {count} tools are linked at their locked versions in {path}."
    npm_missing_hint: str = (
        "A Node tool installs with npm, and the installer provisions no runtime: install Node.js at "
        "the version in .node-version, which brings npm."
    )
    path_hint: str = (
        'Note: {path} is not in your PATH.\nAdd to your shell config:  export PATH="{path}:$PATH"'
    )


@dataclass(frozen=True)
class OpenSpecMessages:
    missing_hint: str = (
        "OpenSpec is a pinned Node tool: install it with "
        "`uv run devops install-tools --tool openspec --only-missing`."
    )
    command_timed_out: str = "{command} ran past its {timeout} timeout and was stopped."
    command_failed: str = "{command} failed with exit code {code}: {reason}"
    check_passed: str = "OpenSpec check passed."
    check_failed: str = "OpenSpec check found {count} problem(s)."
    finding_line: str = "{check}: {detail}"
    skill_differs: str = (
        "{path} is not what `openspec update` writes under the isolated custom profile: run "
        "`uv run devops openspec regenerate` and commit the result."
    )
    skill_missing: str = (
        "{path} is what `openspec update` writes under the isolated custom profile and is not in "
        "the tree: run `uv run devops openspec regenerate` and commit the result."
    )
    skill_unexpected: str = (
        "{path} is not written by `openspec update` under the isolated custom profile: delete it, "
        "or run `uv run devops openspec regenerate` and commit the result."
    )
    skill_tree_missing: str = (
        "No file matches {pattern}. `openspec update` writes a skill tree only where one exists, "
        "so `uv run devops openspec regenerate` cannot write it back: restore it from git."
    )
    overlap: str = (
        '{spec}: the requirement "{requirement}" is rewritten by {changes}: both would archive '
        "and the later would overwrite the earlier with no signal, so fold the items into one "
        "change or order them with a blocker, so that the second waits until the first archives."
    )
    config_missing: str = (
        "{path} is missing: it carries the planning conventions every agent reads through "
        "`openspec instructions`."
    )
    regenerated: str = "Regenerated the OpenSpec skills under the isolated custom profile."
    archived: str = "Archived {change}. Every spec and change validates."
    archive_failed: str = (
        "{command} failed with exit code {code}. The reason is above. The validation did not run."
    )
    archive_left_invalid: str = (
        "{command} failed with exit code {code}. The archive is applied. Fix the specs that the "
        "tool names above. Then run `uv run devops openspec check`. Do not run the archive again."
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
    public_key_not_found: str = "Public key not found: {pub_path}"
    failed_to_register_key: str = "Failed to register key on GitHub: {error}"
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
    worktrees_dry_run_confirm: str = (
        "--dry-run makes no change, so it cannot be used with --confirm."
    )
    worktrees_add_heading: str = "Commands that `devops repos worktrees add` runs:"
    worktrees_add_dry_run_notes: tuple[str, ...] = (
        "A dry run reads local git only. Run without --dry-run to read origin and to create the "
        "worktree.",
        "If origin holds a staged branch for the issue, the run reads its authors with the log "
        "command and adds the worktree on that branch with --track.",
        "If a local branch of the new name exists, no worktree uses it, and origin holds all its "
        "commits, the run deletes that stray branch first.",
        "A run also claims the issue for an agent with the label owner/agent on the roadmap of "
        "origin. The claim lists the requests of the label write.",
    )
    worktrees_add_created: str = "Created worktree {path} on branch {branch}."
    worktrees_add_took_over: str = (
        "Took over the staged branch {branch} in worktree {path}. Commits by the App: {commits}."
    )
    worktrees_add_not_reclaimed: str = "Merged worktrees were not reclaimed: {reason}"
    worktrees_add_claimed: str = "Claimed #{issue} for an agent."
    worktrees_add_not_claimed: str = "#{issue} is not claimed for an agent: {reason}"
    worktrees_add_no_origin: str = (
        "The repository has no remote named origin, so the branches of origin cannot be read. "
        "Add the remote."
    )
    worktrees_add_held_by_worktree: str = (
        "Issue {issue} is held by the worktree {path} on branch {branch}."
    )
    worktrees_add_held_by_directory: str = (
        "Issue {issue} is held by the directory {path}, where its worktree goes."
    )
    worktrees_add_held_by_author: str = (
        "Issue {issue} is held by the branch origin/{branch}. It has a commit by {author}, not by "
        "the App ({bot})."
    )
    worktrees_add_held_no_app: str = (
        "Issue {issue} is held by the branch origin/{branch}. The setting "
        "service.github_app.slug is not set, so no commit counts as a commit by the App."
    )
    worktrees_add_held_no_commits: str = (
        "Issue {issue} is held by the branch origin/{branch}. It has no commit past "
        "origin/main, so nothing shows that the App staged it."
    )
    worktrees_add_held_by_pushed: str = "Issue {issue} is held by a pushed branch: {branches}."
    worktrees_add_held_by_branches: str = (
        "Issue {issue} is held by more than one branch of origin: {branches}."
    )
    worktrees_add_staged_differs: str = (
        "Issue {issue} has the staged branch origin/{branch}. Its {option} is '{staged}', not "
        "'{given}'. Use --{option} {staged}, or leave the option out."
    )
    worktrees_add_needs_branch_options: str = (
        "No branch of origin holds issue {issue}. Give --type and --slug to name the new branch."
    )
    worktrees_add_dry_run_needs_options: str = (
        "--dry-run cannot read the branches of origin. Give --type and --slug."
    )
    worktrees_add_stray_deleted: str = (
        "Deleted the stray local branch {branch} at {commit}. No worktree uses it, and origin "
        "holds all its commits."
    )
    worktrees_add_stray_unpushed: str = (
        "The local branch {branch} has {count} commit(s) that origin does not hold, and no "
        "worktree uses it. Push the commits or delete the branch, then try again."
    )
    worktrees_add_git_failed: str = "`git {command}` failed: {reason}"
    worktrees_add_bad_type: str = "'{type}' is not a branch type. Allowed types: {types}."
    worktrees_add_bad_slug: str = (
        "'{slug}' is not a slug. Use lowercase letters and digits joined by single hyphens."
    )
    worktrees_prune_heading: str = "Requests that `devops repos worktrees prune --confirm` makes:"
    worktrees_prune_dry_run_notes: tuple[str, ...] = (
        "A dry run reads local git only. Run without --dry-run to read the pull requests, and "
        "with --confirm to remove.",
    )
    worktrees_prune_preview: str = (
        "Preview: {would_remove} removable ({size}), {refused} refused. Run with --confirm to "
        "remove."
    )
    worktrees_prune_done: str = (
        "Prune complete: {removed} removed, {refused} refused, {failed} failed, {size} freed"
    )


@dataclass(frozen=True)
class K8sMessages:
    grafana_password_missing: str = (
        "The Grafana admin password is not in the keyring (grafana_password). Store it with "
        "'devops config set grafana.password', or adopt it from the cluster with "
        "'devops k8s push-secrets'."
    )
    current_context: str = "Current Kubernetes context: [bold cyan]{context}[/bold cyan]"
    switched_context: str = "✓ Switched to Kubernetes context: [bold green]{context}[/bold green]"
    no_contexts_found: str = "No Kubernetes contexts found in Kubeconfig."
    cluster_not_reachable: str = "Kubernetes cluster is not reachable."
    tunnel_started: str = (
        "Forwarding {host} to {listener} (pid {pid}). cloudflared writes its log to {log}."
    )
    tunnel_already_running: str = "A forward to {host} already runs on {listener} (pid {pid})."
    tunnel_context_written: str = (
        "Wrote the kubeconfig context {context}. Use it with 'kubectl --context {context}' or "
        "'devops k8s switch-context {context}'."
    )
    tunnel_stopped: str = "Stopped the forward to {host} (pid {pid})."
    tunnel_none_running: str = "No tunnel forward runs."
    tunnel_forward: str = "Forward: pid {pid}, {host} to {listener}, started {started}."
    tunnel_none_recorded: str = "No tunnel forward is recorded."
    tunnel_port_listening: str = "Port {listener}: listening."
    tunnel_port_closed: str = "Port {listener}: not listening."
    tunnel_api_answers: str = "API server (context {context}): answers."
    tunnel_api_silent: str = "API server (context {context}): does not answer."
    tunnel_api_unchecked: str = (
        "API server: not checked. Give --context, or start the forward with --context."
    )
    proxy_service_unreachable: str = (
        "Did not write {key}: the API server cannot reach {address}. A NetworkPolicy can admit "
        "only pods, and then the API server reaches only the pods on its own node. Use "
        "'--addressing fqdn', or 'devops k8s port-forward'."
    )
    proxy_service_check_failed: str = (
        "Did not write {key}: the check of {address} through the API server failed: {error}"
    )
    start_minikube_tip: str = (
        "Start it with: [cyan]minikube start --driver=docker --cni=calico[/cyan]"
    )
    starting_minikube: str = "[bold cyan]Starting minikube cluster...[/bold cyan]"
    failed_start_minikube: str = "Failed to start minikube cluster."
    minikube_not_running: str = (
        "minikube is not running. Start with: minikube start --driver=docker --cni=calico"
    )
    adding_helm_repos: str = "[bold]Adding Helm repositories...[/bold]"
    removing_stack_namespaces: str = "[bold]Removing all stack namespaces...[/bold]"
    removing_infra_namespaces: str = "[bold]Removing infra namespaces...[/bold]"
    removing_llm_namespace: str = "[bold]Removing llm namespace...[/bold]"
    kube_linter_passed: str = "Kube-linter audit passed: no security warnings."
    kube_linter_not_run: str = "Kube-linter audit {status}: {reason}. The manifest was not audited, so the check did not pass."
    kubeconform_not_run: str = "Kubeconform validation {status}: {reason}. kubeconform validated no manifest, so the check did not pass."
    popeye_executing: str = "[dim]Executing Popeye K8s cluster health sanitizer...[/dim]"
    popeye_passed: str = "Popeye cluster audit passed: no health warnings."
    popeye_not_run: str = (
        "Popeye cluster audit {status}: {reason}. Popeye did not run, so the check did not pass."
    )
    pluto_passed: str = "Pluto API check passed: no deprecated K8s APIs."
    image_pins_resolved: str = (
        "Each of the {count} image(s) that the Argo CD Applications pin resolves in its registry."
    )
    image_pins_failed: str = (
        "{count} image(s) that the Argo CD Applications pin do not resolve: {detail}"
    )
    image_pins_failure: str = "{image} (Application {applications}, registry {registry}): {error}"
    image_pins_latest: str = "{count} image(s) that the Argo CD Applications name use the latest tag and no digest, so each pull can get a different image. Set a version tag or a digest: {detail}"
    image_pins_latest_image: str = "{image} (Application {applications})"
    image_pins_managed: str = (
        "Image Updater moves these repositories, so they are not pins: {repositories}"
    )
    image_pins_local: str = "Only the cluster or this host reaches the registry of these images, so they are not resolved: {images}"
    image_pins_dry_run: str = "Each image that the renders name is then resolved with: {command}"
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
    post_helm_delete_skipped: str = (
        "Skipped {path}: the cluster does not serve kind '{kind}' ({api_version})."
    )
    post_helm_apply_failed: str = (
        "Failed to apply {path}: the cluster does not serve kind '{kind}' ({api_version})."
    )
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
    gpu_node_without_total: str = (
        "GPU node {node} has no {vram_label} label, so no Ollama tier schedules there. "
        "Label it: kubectl label node {node} {vram_label}=<N>Gi"
    )
    gpu_node_total_not_accepted: str = (
        "GPU node {node} is labelled {vram_label}={value}, which no Ollama tier accepts. "
        "Label it with a value a tier accepts: kubectl label node {node} {vram_label}=<N>Gi"
    )
    gpu_node_architecture_not_accepted: str = (
        "GPU node {node} has {arch_label}={arch}, but the Ollama tiers that accept "
        "{vram_label}={value} need one of: {accepted}."
    )
    no_ollama_tier_schedules: str = (
        "No node satisfies any Ollama tier, so no Ollama pod will schedule."
    )
    gpu_nodes_unreadable: str = (
        "Could not read the cluster's nodes, so deploy-stack could not check the GPU labels "
        "the Ollama tiers need."
    )
    push_plan_read: str = (
        "Plan only: read {sources}{context}; wrote nothing. "
        "--dry-run lists the requests without making any."
    )
    push_plan_sources: str = "the keyring and the cluster"
    push_dry_run_heading: str = (
        "Dry run: no request was made. A push would make these requests, in order:"
    )
    push_dry_run_writes: str = (
        "The writes, from the first keyring write on, run only when every key resolves: no "
        "source missing or invalid, and no live value differing without --rotate. "
        "--plan reads the keyring, gh and the cluster to show each key's state."
    )
    job_runner_needs_repo: str = (
        "A runner Job needs the repository it acts on. Pass --repo owner/name: the Job's GitHub "
        "token then names only that repository. No Job was created."
    )
    job_repo_needs_runner: str = (
        "--repo sets the repository of a runner Job. Use it with --template runner. No Job was "
        "created."
    )
    job_runner_running: str = (
        "A runner Job of {repo} has not ended: {names}. A second runner Job for the repository "
        "could push to the same branch. Wait for the Job to end, or follow it with: "
        "kubectl -n devops logs -f job/<name>. No Job was created."
    )
    job_cronjob_missing: str = (
        "CronJob devops/{cronjob} not found. Deploy it first: "
        "devops k8s deploy-stack --stack devops"
    )
    job_api_refused: str = (
        "The Kubernetes API refused to {action} in namespace devops: HTTP {status} {reason}"
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
    table_title_image_pins: str = "Image Pins of the Argo CD Applications"
    table_title_kubeconform: str = "Kubeconform Strict Schema Validation"
    table_title_nodes: str = "Nodes"
    node_ready: str = "Ready"
    node_not_ready: str = "NotReady"
    volume_reclaimed: str = "PersistentVolume '{name}' {action} successfully."
    volume_reclaim_aborted: str = "PersistentVolume '{name}' reclaim aborted."
    volume_reclaim_dry_run_heading: str = "Planned Kubernetes Volume Reclaim API Requests:"
    volume_move_bad_ref: str = "Give the claim as NAMESPACE/CLAIM, not '{ref}'."
    volume_move_claim_missing: str = "Claim {namespace}/{claim} does not exist."
    volume_move_claim_not_bound: str = (
        "Claim {namespace}/{claim} is {phase}, not Bound. The move copies only a bound claim."
    )
    volume_move_not_local: str = (
        "Volume {volume} has no node affinity to one node. It is not a local volume, so it does "
        "not need a move."
    )
    volume_move_no_pods: str = (
        "No pod mounts claim {namespace}/{claim}. Start its workload first: the move stops and "
        "starts the workload, and makes sure that its pods run on the target node after the move."
    )
    volume_move_unsupported_owner: str = (
        "Pod {pod} belongs to {owner}. The move can stop and start only a Deployment or a "
        "StatefulSet."
    )
    volume_move_retention_delete: str = (
        "StatefulSet {name} deletes its claims when it scales down "
        "(persistentVolumeClaimRetentionPolicy.whenScaled: Delete). A scale to zero would delete "
        "claim {claim}."
    )
    volume_move_leftovers: str = (
        "An earlier move left {names}. Make sure that they hold no data that you need, then "
        "delete them."
    )
    volume_move_not_on_control_plane: str = (
        "Volume {volume} is on node {node}, which is not a control-plane node. To move it to "
        "another worker node, name that node with --to-node."
    )
    volume_move_unknown_node: str = "Node {node} does not exist."
    volume_move_target_control_plane: str = (
        "Node {node} is a control-plane node. The move puts a volume only on a worker node."
    )
    volume_move_target_is_source: str = "Volume {volume} is on node {node} already."
    volume_move_target_unavailable: str = "Node {node} is not Ready, or it is cordoned."
    volume_move_no_target: str = "No worker node is Ready and schedulable for the volume."
    volume_move_unknown_application: str = (
        "Argo CD Application {application}, which the tracking annotation names, does not exist "
        "in namespace {namespace}."
    )
    volume_move_refused: str = (
        "The move of claim {namespace}/{claim} cannot start. It changed nothing."
    )
    volume_move_read_failed: str = (
        "The plan of the move of claim {namespace}/{claim} failed. It changed nothing: {reason}"
    )
    volume_move_request_failed: str = "`{request}` exited {code}: {detail}"
    volume_move_request_timeout: str = "`{request}` did not end within {seconds:g} s."
    volume_move_bad_output: str = "`{request}` did not return JSON: {detail}"
    volume_move_unbound_copy: str = "Claim {claim} has no volume after its pod started."
    volume_move_digest_unreadable: str = "The digest of pod {pod} is not complete: {output}"
    volume_move_digest_differs: str = (
        "The two sides are different ({fields}). The destination is not a full copy."
    )
    volume_move_digest_equal: str = (
        "The two sides are equal: {entries} entries, {files} files, {bytes} bytes of regular "
        "files, and equal metadata and content digests."
    )
    volume_move_copy_retry: str = "The copy stopped ({reason}). Empty /dst and copy one more time."
    volume_move_save_failed: str = "Cannot save claim {claim} to {path}: {reason}"
    volume_move_saved: str = "Saved claim {namespace}/{claim} to {path}."
    volume_move_placement: str = (
        "After the move, the pods of claim {claim} must run on node {node}, but they are: {pods}."
    )
    volume_move_interrupted: str = "the move was interrupted"
    volume_move_step_pause: str = (
        "Pause automated sync of the Argo CD Applications {applications}, from the top down."
    )
    volume_move_step_no_pause: str = (
        "Pause nothing: no Argo CD Application tracks the claim or its workloads."
    )
    volume_move_step_destination: str = (
        "Create claim {claim} ({size}, {storage_class}) and pod {pod} on node {node}, and wait "
        "until the pod is Ready."
    )
    volume_move_step_stop: str = (
        "Scale {workloads} to 0, and wait until these pods are gone: {pods}."
    )
    volume_move_step_source: str = (
        "Start pod {pod} with claim {claim} read-only on node {node}, and wait until it is Ready."
    )
    volume_move_step_copy: str = (
        "Copy /src of pod {source} to /dst of pod {destination} with GNU tar through the API "
        "server. If the stream stops, empty /dst and copy one more time."
    )
    volume_move_step_compare: str = (
        "Compare the two sides: the entries, the files, the bytes of regular files, a metadata "
        "digest and a content digest. Stop at a difference."
    )
    volume_move_step_retain: str = (
        "Set the reclaim policy of the new volume of claim {claim} and of volume {volume} to "
        "Retain."
    )
    volume_move_step_delete_pods: str = "Delete the pods {source} and {destination}."
    volume_move_step_delete_claim: str = (
        "Save claim {namespace}/{claim} and delete it. This is the point of no return."
    )
    volume_move_step_rebind: str = (
        "Delete claim {move_claim}, and reserve its volume for claim {namespace}/{claim}."
    )
    volume_move_step_recreate: str = (
        "Create claim {namespace}/{claim} again from the saved claim, bound to the new volume, "
        "put back its last-applied configuration if it has one, and wait until it is Bound."
    )
    volume_move_step_start: str = (
        "Scale {workloads} again, wait until the pods are ready, and make sure that they run on "
        "node {node}."
    )
    volume_move_step_resume: str = (
        "Resume automated sync of the Argo CD Applications {applications}."
    )
    volume_move_step_no_resume: str = "Resume nothing: the move paused no Argo CD Application."
    volume_move_step_line: str = "Step {number}/{total}: {text}"
    volume_move_undo_resume: str = "Resume automated sync of Application {application}"
    volume_move_undo_delete: str = "Delete {kind} {name}"
    volume_move_undo_scale: str = "Scale {workload} back to {replicas}"
    volume_move_undo_reclaim: str = "Set the reclaim policy of volume {volume} back to {policy}"
    volume_move_undo_line: str = "Undo: {text}."
    volume_move_plan_heading: str = (
        "Plan of the move of claim {namespace}/{claim}. The plan only reads; it changed nothing."
    )
    volume_move_plan_claim: str = (
        "Claim: Bound to volume {volume} ({size}, {storage_class}) on node {node}, reclaim "
        "policy {policy}."
    )
    volume_move_plan_target: str = "Target node: {node}, {free} free."
    volume_move_plan_workloads: str = (
        "Workloads that mount the claim: {workloads}. Their pods: {pods}."
    )
    volume_move_plan_argocd: str = (
        "Argo CD Applications that track the claim or its workloads: {applications}. The move "
        "pauses: {paused}."
    )
    volume_move_plan_no_argocd: str = "Argo CD: no Application tracks the claim or its workloads."
    volume_move_plan_steps: str = "Steps:"
    volume_move_plan_point_of_no_return: str = (
        "Step {number} deletes the old claim. Before that step, a failure undoes the steps that "
        "ran. From that step on, a failure leaves Argo CD paused and names the saved claim, "
        "because a self-heal would make an empty claim."
    )
    volume_move_start: str = "Start the move of claim {namespace}/{claim} to node {node}."
    volume_move_done: str = "Moved claim {namespace}/{claim} to node {node}."
    volume_move_done_new_volume: str = (
        "New volume: {volume}, reclaim policy Retain, bound to claim {namespace}/{claim}."
    )
    volume_move_done_old_volume: str = (
        "Old volume: {volume} on node {node}, reclaim policy Retain. It keeps the old data until "
        "a person deletes it with: {command}"
    )
    volume_move_done_saved: str = "Saved claim: {path}"
    volume_move_undone: str = "The move stopped at step {step}: {reason}"
    volume_move_undone_steps: str = "The move undid these steps: {steps}."
    volume_move_undone_nothing: str = "The move had changed nothing yet."
    volume_move_undo_failed: str = "These undo steps failed. Do them by hand: {failures}"
    volume_move_stranded: str = (
        "The move stopped at step {step}, after the old claim was deleted: {reason}"
    )
    volume_move_stranded_paused: str = (
        "Argo CD stays paused: {applications}. Do not resume it before claim "
        "{namespace}/{claim} is Bound again, because a self-heal would make an empty claim."
    )
    volume_move_stranded_volumes: str = (
        "Old volume {old_volume}: reclaim policy Retain, with the old data. New volume "
        "{new_volume}: with the copy."
    )
    volume_move_stranded_remaining: str = (
        "Do these steps by hand (k8s/README.md, Local-Path Volume Placement, Finish a stopped "
        "move):"
    )
    volume_move_dry_run_heading: str = (
        "Dry run: no request was made. A move would make these requests, in order:"
    )
    volume_move_dry_run_undo: str = (
        "Before the old claim is deleted, a failed request starts the undo, in reverse order: "
        "it deletes the copy pods and claim {claim}, scales the workloads back, sets the reclaim "
        "policies back and resumes Argo CD."
    )


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
    inventory_entry_missing: str = (
        "{entry}: the document inventory lists it, but no file matches, so its command lines "
        "cannot be checked."
    )
    argv_unknown_command: str = "unknown command '{token}' under '{command_path}'"
    argv_unknown_option: str = "unknown option '{token}' for '{command_path}'"
    argv_unexpected_argument: str = "unexpected extra argument '{token}' for '{command_path}'"
    synced_readme: str = "✓ Synchronized Command Matrix table in {path}"
    unsupported_format: str = (
        "Unsupported documentation format: {format}. Supported: markdown, json"
    )


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
    state_unavailable: str = "State unavailable (run tofu init)."
    drift_in_sync: str = "✓ Configuration and state agree on all {count} resource(s)."
    drift_summary: str = (
        "{missing} declared but not in state, {orphaned} in state but not declared, "
        "{drifted} drifted, {synced} in sync."
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
    tflint_not_run: str = (
        "TFLint lint {status}: {reason}. tflint linted no file, so the check did not pass."
    )
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
    draft_created: str = (
        "Opened a draft pull request: {url}. When its checks pass, mark it ready with devops pr "
        "ready."
    )
    draft_created_into: str = (
        "Opened a draft pull request into {base}. When its checks pass, mark it ready with "
        "devops pr ready."
    )
    # What `devops pr create` names as the base when --base is not given.
    create_default_base: str = "the default branch"
    status_closing_unread: str = (
        "The issues that the pull request closes could not be read: {error}"
    )
    status_not_set: str = (
        "Pull request #{number} is {state}, but the Status of its item was not set: {error}"
    )
    labels_not_set: str = (
        "Pull request #{number} is open, but the labels of its title were not added: {error} "
        "To add a label by hand, run: devops gh api -X POST repos/{repo}/issues/{number}/labels "
        "-f labels[]=<label>"
    )
    labels_dry_run_heading: str = "Would add the labels of the title to the new pull request:"
    labels_dry_run_condition: str = "the pull request opens and the labels file declares it"
    labels_unreadable: str = "{path} can't be read as label specs: {error}"
    labels_refused: str = "{labels} could not be added: {error}"
    labels_scope_undeclared: str = (
        "The scope `{scope}` of the title has no label: {path} does not declare {label}. "
        "The pull request gets no scope label."
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
    grounding_not_into_default: str = (
        "PR #{number} is not grounded: it targets {base}, not the default branch {default}. "
        "Change its base with devops pr edit {number} --base {default}."
    )
    grounding_no_default_branch: str = (
        "PR #{number} is not grounded: GitHub names no default branch for {repo}."
    )
    grounding_closing_unread: str = (
        "PR #{number} is not grounded: the issues it closes could not be read ({error})."
    )
    grounding_closes_no_issue: str = (
        "PR #{number} is not grounded: it closes no issue. Put Closes #<issue> in its body for "
        "the one issue it delivers."
    )
    grounding_closes_several_issues: str = (
        "PR #{number} is not grounded: it closes {count} issues ({issues}), and a PR delivers "
        "exactly one."
    )
    grounding_closes_foreign_issue: str = (
        "PR #{number} is not grounded: it closes {issue}, which is not an issue of {repo}."
    )
    grounding_closes_closed_issue: str = (
        "PR #{number} is not grounded: it closes #{issue}, which is not open."
    )
    grounding_issue_not_item: str = (
        "PR #{number} is not grounded: #{issue} is not a roadmap item: it holds no priority "
        "label. Run devops roadmap intake on it."
    )
    grounding_change_not_archived: str = (
        "PR #{number} is not grounded: it adds no {folder} for #{issue}. Archive the change in"
        " the last commit of the PR with uv run devops openspec archive {change}."
    )
    grounding_record_written: str = (
        "PR #{number} is not grounded: it changes {paths}. Only the archive of the change of"
        " #{issue} writes {specs}/ and {archive}/, and only in {folder}."
    )
    grounding_files_unread: str = (
        "PR #{number} is not grounded: the files it changes could not be read ({error})."
    )
    grounding_changes_dir_unread: str = (
        "PR #{number} is not grounded: {path}/ could not be read at its base ({error})."
    )
    changed_files_unread: str = "Could not read the files PR #{number} changes ({error})."
    hardening_report_title: str = "Defect Pull Request Hardening Audit"
    hardening_report_no_defects: str = "No merged defect pull requests found matching criteria."
    hardening_report_pr_not_defect: str = "PR #{number} is not classified as a defect PR."
    hardening_report_passed: str = (
        "All {count} defect PRs satisfied hardening requirements on declared surfaces."
    )
    hardening_report_failed: str = (
        "{missing_count} of {total_count} defect PRs lack additions on declared hardening surfaces."
    )
    hardening_report_single_passed: str = (
        "PR #{number} passed hardening audit: additions present on declared surface(s): {surfaces}"
    )
    hardening_report_single_failed: str = (
        "PR #{number} failed hardening audit: no additions on declared hardening surfaces."
    )
    hardening_report_empty_files: str = "PR #{number} returned an empty file list from GitHub."


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
    view_traces_tempo: str = "\n[dim]To query traces via Tempo HTTP API: {url}[/dim]"
    emitting_span: str = (
        "[bold]Emitting test trace span '[cyan]{name}[/cyan]' to [cyan]{endpoint}[/cyan]...[/bold]"
    )
    span_emitted_success: str = "Test span emitted successfully! (Span ID: [cyan]{span_id}[/cyan], Duration: {elapsed_ms:.1f}ms)"
    view_tempo_service: str = "[dim]Query in Tempo: {url} (Service: {service})[/dim]"
    tempo_api_link: str = "[bold]Tempo HTTP API:[/bold] [link={url}]{url}[/link]"
    profile_devops_only: str = (
        "telemetry profile runs only a devops-cli command, whose first word is 'devops' "
        "(e.g. 'devops k8s contexts'); pass --trace-id to show a trace already in Tempo."
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
    zizmor_executing: str = "Auditing GitHub Actions workflows in '{target}' with zizmor..."
    zizmor_passed: str = "✓ zizmor found nothing in the workflows."
    zizmor_title: str = "zizmor Workflow Audit: {target}"
    zizmor_blocking: str = (
        "{count} finding(s) from {rules} block the gate; each row links zizmor's remedy."
    )
    zizmor_reported: str = (
        "{count} finding(s) from other zizmor audits are reported and do not block."
    )
    zizmor_failed: str = "zizmor could not run (exit {code}): {detail}"
    zizmor_not_applicable: str = "No GitHub Actions workflows or action files in the target"
    uv_audit_not_a_directory: str = (
        "{target} is not a directory. uv audit audits the project of a directory."
    )
    kubeconform_not_applicable: str = "No Kubernetes manifest in the target"
    semgrep_executing: str = "Executing Semgrep AST scan on '{target}' (config: {config})..."
    semgrep_passed: str = "✓ No static AST pattern flaws detected."
    semgrep_default_flaw: str = "Code pattern flaw detected by Semgrep"
    semgrep_default_message: str = "Code pattern flaw detected by Semgrep"
    semgrep_batch_failed: str = "batch {batch} of {batches}, {files} files: {reason}"
    semgrep_file_not_scanned: str = "Semgrep did not list the file as scanned"
    injection_executing: str = "Scanning '{target}' for prompt-injection smuggling vectors..."
    injection_passed: str = "✓ No prompt-injection smuggling vectors detected."


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
    no_project_key: str = (
        "No managed SSH key with the prefix '{prefix}' exists in {key_dir}. "
        "Run 'devops ssh generate' to make one."
    )
    list_all_tip: str = "Add '--all' to show the keys of all projects."
    all_with_prefix: str = "Use '--all' or '--prefix'. Do not use both."
    no_managed_keys_pattern: str = (
        "No managed SSH keys found (expected: PREFIX-id_ed25519-YYYYMMDD or id_ed25519-YYYYMMDD)."
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
    scan_status: str = "{scanner} scan status: {status}"
    scan_reason: str = "Reason: {reason}"
    scan_gave_no_result: str = "The scan gave no result. Do not report the target as clean."
    scan_no_findings: str = "No findings."
    scan_findings: str = "Findings ({count}):"
    scan_finding: str = "- [{severity}] {location}: {title}"
    scan_finding_fix: str = "{finding} ({fix})"


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
    helm_records_request_failed: str = "`{request}` failed: {detail}"
    helm_records_request_timeout: str = "`{request}` did not answer in {seconds:g} s."
    helm_records_dry_run_heading: str = (
        "Dry run: no request was made. Retiring the Helm release records would make these "
        "requests, in order:"
    )
    helm_records_table_title: str = "Helm release records of charts that Argo CD renders"
    helm_records_none: str = "No Helm release record belongs to a chart that Argo CD renders."
    helm_records_qualifies: str = "retire {count} record(s)"
    helm_records_refused: str = "keep: Argo CD did not apply {count} object(s)"
    helm_records_unapplied: str = (
        "Release {release} in {namespace}: Argo CD did not apply {object}. Sync Application "
        "{application}, then run this command again."
    )
    helm_records_kept: str = (
        "Kept, because no Application renders the release or an operator owns the record: "
        "{releases}"
    )
    helm_records_confirm_hint: str = (
        "Nothing was deleted. Run the command again with --confirm to delete the {count} "
        "record(s) of the {releases} release(s) that qualify."
    )
    helm_records_retired: str = "Deleted {count} record(s) of release {release} in {namespace}."
    helm_records_done: str = (
        "Helm forgets {releases} release(s). Every object stays, and Argo CD keeps applying it."
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
    path_not_found: str = (
        "The path '{path}' does not exist. Check the name: a path that is not there gives no test."
    )
    directory_without_tests: str = (
        "No test can be selected for the directory '{directory}'. Name a directory of tests/ "
        "that holds a test module, a directory of src/, or a file."
    )
    selection_fallback: str = (
        "Falling back to the full suite because the changed sources map to no tests."
    )
    selection_empty: str = (
        "Refusing to report success without running any tests. Re-run with --fallback "
        "to verify via the full suite, or add a covering test."
    )
    repeat_failed: str = "Run {run}/{runs} failed with seed {seed}. Reproduce it with: {command}"
    repeat_needs_targets: str = (
        "--repeat needs test files to narrow the run; shuffling the whole suite is not "
        "supported yet."
    )
    repeat_seed_unavailable: str = "Could not read HEAD to derive a shuffle seed; pass --seed."
    run_timed_out: str = (
        "{command} ran past its {timeout} timeout and was stopped with every process it started."
    )
    test_settings: str = "test settings (pytest timeout and conftest environment)"
    pytest_coverage: str = "pytest & coverage"
    ruff_check: str = "ruff check"
    ruff_format: str = "ruff format"
    mypy_check: str = "mypy (py314 strict)"
    uv_check: str = "uv check"
    uv_lock: str = "uv lockfile freshness"
    uv_build: str = "uv build (wheel and sdist)"
    uv_outdated: str = "uv tree --outdated"
    dependency_audit: str = "uv audit and npm audit"
    deptry: str = "deptry"
    deps: str = "deptry"
    constructs: str = "ast-grep scan (network constructs and working-directory reads in src, elapsed-time bounds in tests)"
    bandit_scan: str = "bandit security scan"
    actionlint: str = "actionlint (github workflows)"
    zizmor: str = "zizmor (github workflow security)"
    audit_vulnerable: str = "Dependency audit found vulnerabilities ({tool} audit exited {code})."
    audit_not_run: str = (
        "Dependency audit could not run ({tool} audit exited {code}); {tool}'s error is above."
    )
    docs_validation: str = "docs validation"
    devcontainer_validation: str = "devcontainer validation"
    openspec_validation: str = "openspec validation"
    git_transcripts: str = "git transcripts (recorded again with the real git)"
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
    gate_slot_wait: str = (
        "Waiting for a CI gate slot. Allowed at one time: {slots}. Held by: {holders}."
    )
    gate_slot_holder: str = "process {pid} in {worktree}"
    gate_slot_holder_unknown: str = "another run"
    test_budget_exceeded: str = "Tests took {duration}, over the {budget} budget. Slowest tests:"
    job_time_title: str = "{job}: last runs of {workflow} on {branch}"
    job_time_ok: str = (
        "The last {count} runs of {job} took {mean:.0f} s on average. The limit is {limit:.0f} s."
    )
    job_time_over: str = (
        "Over the limit: the last {count} runs of {job} took {mean:.0f} s on average, "
        "and the limit is {limit:.0f} s."
    )
    job_time_short: str = (
        "Only {found} of the last {wanted} runs of {job} could be read from {workflow} on "
        "{branch}, so the mean says nothing yet."
    )
    job_time_no_repo: str = (
        "No repository to read: the checkout has no origin remote. Give one with --repo."
    )
    job_time_dry_run_heading: str = (
        "Would read the time of {job} in the last runs of {workflow} on {branch}"
    )
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
    coverage_index_stale: str = (
        "The coverage index is stale: {file} changed since it was built and can change what any "
        "test covers, so tests are selected by name and import. Run `devops ci coverage "
        "--build-index` to rebuild it."
    )
    coverage_index_helper_removed: str = (
        "{file} is gone since the coverage index was built: what it registered, and which tests "
        "imported it, can no longer be read, so no test selection can cover it."
    )
    selection_trigger_full_run: str = (
        "{file} can change the outcome of tests that never import it. "
        "Running the full test suite. Run `devops ci coverage --build-index` to update."
    )
    selection_trigger_refusal: str = (
        "Refusing to narrow tests because {file} changed. Run without --no-fallback "
        "or run the full suite."
    )
    mutate_needs_target: str = (
        "Name the source files to mutate, or pass --changed to mutate the functions changed "
        "since the merge base with --base."
    )
    mutate_nothing: str = (
        "Nothing to mutate: the selection holds no function mutmut mutates. mutmut leaves out "
        "__new__, __getattribute__, __setattr__ and a decorated function unless its one "
        "decorator is @staticmethod or @classmethod."
    )
    mutate_base_refused: str = "Refusing to diff against '{base}': it is not a git revision name."
    mutate_base_missing: str = (
        "Cannot diff against '{base}': it names no commit in this clone. Fetch it, or pass "
        "--base a branch, tag or commit the clone has."
    )
    mutate_survivor: str = "{path}:{line} {qualname}"
    mutate_counts: str = "Mutants of the selected functions: {counts}."
    fail_to_pass_test_line: str = "  {status} on base: {test_id}{detail}"
    fail_to_pass_summary: str = (
        "{failed} failed on base ({failed} failed and {passed} passed in {files}; "
        "{errored} errored)."
    )
    fail_to_pass_no_tests: str = (
        "The fix changes no tests/**/test_*.py file. A fix adds or changes a test that fails on "
        "its base."
    )
    fail_to_pass_none_failed: str = (
        "A fix needs at least one changed test that fails in the call phase on base ({tests})."
    )
    fail_to_pass_could_not_run: str = (
        "The fail-to-pass replay could not run on base: pytest exited with status {status} "
        "replaying {files}. Merge the change to the test harness or to the dependencies first, in "
        "a pull request that is not a fix. Then replay this fix against the new base."
    )
    fail_to_pass_replay_output: str = "pytest's last output: {output}"
    fail_to_pass_worktree_failed: str = (
        "The replay could not check out {base} as a git worktree: {detail}"
    )


@dataclass(frozen=True)
class DevcontainerMessages:
    already_exists: str = "devcontainer.json already exists: {path}"
    bootstrap_k8s_deploy_hint: str = "Deploy the stack once the keyring is unlocked: devops k8s deploy-stack --stack {stack} --context {context}"
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
    # The Service acts as the GitHub App (ADR 0015), so it does not start without the App.
    github_app_unset: str = (
        "Configuration error: the Service acts as a GitHub App, so {settings} must be configured."
    )
    github_app_key_missing: str = (
        "Configuration error: the Service acts as GitHub App {login}, but the environment holds "
        "no {key_env}. Secret devops/devops-cli gives the key to the Service's pod."
    )
    # Logged once for each webhook delivery, whatever came of it; its record carries the provider,
    # event, action, delivery, repository and outcome (#1386).
    webhook_delivery: str = "Webhook delivery handled."
    # Logged once for each new time a failed Service round names (#1400).
    rounds_paused: str = (
        "No repository starts a Service round before {until}, the time the failed round for "
        "{repo} named; the triggers that arrive until then run as one round per lane of each "
        "repository."
    )
    # Logged when the time a failed round names can't be read: no round waits, and the worker
    # carries on (#1400).
    rounds_pause_unread: str = (
        "Could not read the time the failed Service round for {repo} names, so no round waits "
        "for it: {kind}: {error}"
    )
    # Logged once, at the error level, when GitHub refuses the Service's identity: no round
    # starts and no GitHub request goes out, also after a restart, until a person removes the
    # Service's halt record and restarts it (#2161, #2474).
    identity_refused: str = (
        "GitHub refused the identity {identity} ({kind}: {error}) in the round for {repo}. The "
        "Service stops every job for every repository and sends no GitHub request, also after a "
        "restart, until a person removes its halt record and restarts it."
    )
    # Logged once, at the error level, when the Service starts and finds its halt record (#2474).
    identity_refused_kept: str = (
        "The Service stays halted: {record} records that GitHub refused the identity "
        "{identity}, so no round starts. When the cause is fixed, remove the file and restart "
        "the Service."
    )
    # Logged at the error level when the Service cannot write what a restart must keep (#2474).
    state_unkept: str = (
        "Could not write {record}, so a restart of the Service does not keep what it holds: "
        "{kind}: {error}"
    )
    # Raised when the Service starts and cannot read what it kept before it stopped (#2474).
    state_unreadable: str = (
        "The Service cannot read {record}, which it keeps across a restart: {reason}. Repair or "
        "remove the file, then start the Service again."
    )
    # Logged once each time the hourly GitHub request budget holds the rounds (#2161).
    budget_spent: str = (
        "The Service sent {spent} GitHub requests in the last hour, and its budget is {limit}: "
        "no round starts until the window has room."
    )
    # Raised when a request needs a place in the full window and the Service is stopping (#2547).
    budget_closed: str = (
        "The Service sent {spent} GitHub requests in the last hour, and its budget is {limit}: "
        "the request does not wait for the window, because the Service is stopping."
    )
    # Logged once, when a roadmap job reaches its limit of failed rounds (#2161).
    job_suspended: str = (
        "The roadmap job {job} of {repo} failed {rounds} rounds in a row (causes: {causes}), so "
        "it does not run again until its input changes."
    )
    # Ephemeral chat replies for Mattermost /roadmap slash command (#1395). Each string is one line.
    chat_roadmap_status_round: str = "{repo} [{lane}]: {state}, {pending} pending triggers, last round: {start} to {end} UTC ({result})"
    chat_roadmap_status_no_round: str = (
        "{repo} [{lane}]: {state}, {pending} pending triggers, no round yet"
    )
    chat_roadmap_unknown_repo: str = "Unknown repository {repo}. Known repositories: {repos}."
    chat_roadmap_usage: str = "Usage: /roadmap [status [<repo>]]"


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
    # `devops test run --changed` (#1312).
    unmapped_source: str = (
        "No test module covers {source}: no test module is named for it or imports it."
    )
    changed_whole_suite: str = "No changed file maps to a test module: running the whole suite."
    changed_targets: str = "Running the {count} test target(s) the changes reach:"


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
    argo_image_label: str = "Image:"
    argo_image_in_step: str = "{image} at {digest}"
    argo_image_moved: str = "{image} pins {pinned}, but the tag names {current} now"
    argo_image_unread: str = "{image} pins {pinned}, and the registry gives no digest: {error}"


@dataclass(frozen=True)
class RoadmapMessages:
    preview_only: str = "Nothing was written. Run again with --confirm to make these writes."
    graphql_budget_refused: str = (
        "GraphQL has {remaining} points left until {reset}, and reading {what} costs about "
        "{cost} with {floor} kept in reserve, so the run stopped before reading and spent "
        "nothing on it. Run it again after {reset}."
    )
    graphql_budget_floor: str = (
        "GraphQL has {remaining} points left until {reset}, below the {floor} kept in reserve, "
        "so the read of {what} stopped before page {page}. Run it again after {reset}."
    )
    item_changed: str = (
        "{item}'s {field} is {now} on GitHub but was {read} when this run read it, so someone "
        "changed it since and the run stopped before writing it. Nothing was written; the next "
        "run reads the issue again and plans with that change."
    )
    item_value_unset: str = "unset"
    # The claim of an Item (#2910).
    claim_not_item: str = "#{number} is not an item of the roadmap."
    claim_held: str = (
        "#{number} is claimed by {owner}. An item has one owner at a time: release it first. "
        "Only a person can take an item from the Service."
    )
    claim_closed: str = "#{number} is closed. A closed issue takes no claim."
    claim_no_owner: str = "none"
    claim_plan: str = "Item #{number}: {title}\nOwner: {current} -> {target}"
    claim_plan_only: str = "Plan only: pass --confirm to apply."
    claim_done: str = "Item #{number} is claimed by {owner}."
    claim_released: str = "Item #{number} has no owner."
    claim_unchanged: str = "Item #{number} has the owner {owner} already. Nothing was written."
    claim_release_unchanged: str = "Item #{number} has no owner. Nothing was written."
    item_left_claimed: str = "It is claimed by {owner}."
    # The reasons that both jobs and `devops roadmap explain` give (#2911).
    item_left_not_item: str = (
        "It is not an item of the roadmap: the issue does not exist, is a pull request, or has "
        "no Priority label."
    )
    item_left_closed: str = "It is closed."
    item_heading_unmatched: str = "## Matched no filter"
    # The report of `devops roadmap explain` (#2911).
    explain_title: str = "# {repo} #{number}: {title}"
    explain_title_untitled: str = "# {repo} #{number}"
    explain_job_stage: str = "Stage"
    explain_job_implement: str = "Implement"
    explain_line_yes: str = "{job} job: yes."
    explain_line_no: str = "{job} job: no. {reason}"
    item_left_filter: str = "The filter takes {family} {wanted}. The item has {family} {have}."
    item_left_limit: str = (
        "It passes every rule, but a run takes {limit} item(s) and {limit} item(s) of higher "
        "priority, or of the same priority and a lower number, come first."
    )
    field_value_unknown: str = "{value!r} is not a {field} value; the values are {values}."
    record_unreadable: str = (
        "The job record block of {issue} holds no JSON object of text values, so it reads as "
        "empty, and the next write of its record replaces it."
    )
    # Every comment refine posts starts with its marker (#1758), so a later round finds a reply.
    refine_ready_comment: str = (
        "{marker}\nStatus set to Ready at {sha} (see proposed design in issue body)."
    )
    refine_step_comment: str = "{marker}\n{status}{step}\n\n{details}"
    refine_back_to_new: str = "Status set back to New at {sha}. "
    # The comment that gives an item its next step, by the step's value (#1758).
    refine_step_comments: dict[str, str] = field(
        default_factory=lambda: {
            "person": (
                "Refine cannot set this item to Ready at {sha} until a person answers the "
                "questions below. Reply in a comment or edit the body, and the next refine round "
                "looks at the item again."
            ),
            "split": (
                "The proposal at {sha} needs splitting into {count} items. A person splits the "
                "item into the items below, or replies in a comment or edits the body to keep "
                "one item, and the next refine round looks at the item again."
            ),
            "blocked": (
                "Refine cannot set this item to Ready at {sha} while the items below stay open. "
                "The next refine round looks at the item again when they close, or when a person "
                "replies in a comment or edits the body."
            ),
        }
    )
    # The last line of a next-step comment whose block cites code (#2005).
    refine_block_paths: str = (
        "The next refine round also looks at the item again when a commit on the default "
        "branch changes one of these files: {paths}."
    )
    refine_incomplete: str = (
        "The proposal has no problem statement, no acceptance criterion with its requirement, "
        "scenario, WHEN and THEN, or no answer to the existing-tool question. State the "
        "problem, the requirements with their scenarios, and the open tool that covers the need "
        "or the cost of building it."
    )
    refine_requirement_keyword: str = (
        "The requirement must contain SHALL or MUST, as an OpenSpec requirement does."
    )
    refine_alternatives_question: str = (
        "The alternatives check found that {url} covers this item. Adopt the tool, or keep the "
        "item and give the reason."
    )
    refine_set_back_by_person: str = (
        "A person set the item back to New after refine set it to Ready. A reply that tells "
        "why makes refine look at it again."
    )
    refine_held_status: str = "Status {status}: refine changes only open New and Ready items."
    refine_held_closed: str = "The issue is closed: refine changes only open items."
    # Why a refine round leaves an item that an account without write access opened (#2478).
    refine_outside_author: str = (
        "The author's association with the repository is {association}. A refine round "
        "refines only the items that the owner, a member or a collaborator opened. A person "
        "refines this item with --item {number}."
    )
    refine_author_unknown: str = "unknown"
    # Why a refine round leaves an item that refine commented on too often (#2475).
    refine_comment_cap: str = (
        "Refine wrote {count} comments on this item in the last {hours} hours, which is its "
        "limit. A round after the oldest of these comments is {hours} hours old looks at the "
        "item again. A person refines it now with --item {number}."
    )
    refine_title: str = "# Refinement plan for {repo}"
    # Why a refine round had no web search (#2398).
    refine_web_search_off: str = "Web search is off: {reason}."
    refine_web_off_private: str = "the repository is private"
    refine_web_off_no_key: str = "no Firecrawl key is set"
    refine_web_off_unread: str = "the repository's visibility could not be read"
    refine_none: str = "No items to refine."
    # The warnings of refine for an item whose model call failed or whose investigation stopped.
    refine_item_skipped: str = (
        "Refine skipped #{number} in {repo}: its model call failed ({error}, {reason}, "
        "{violations} schema violation(s))."
    )
    refine_investigation_stopped: str = (
        "Refine's investigation of #{number} in {repo} stopped with no proposal ({reason}); "
        "the item keeps its open questions."
    )
    # The class of a pydantic-ai error, then its message: a stopped run (#2562, #2758).
    run_stop_reason: str = "{error}: {message}"
    # The report's groups, by next step, in the order the report shows them (#1758).
    refine_step_headings: dict[str, str] = field(
        default_factory=lambda: {
            "ready": "## Refined to Ready",
            "person": "## Waiting on a person",
            "split": "## Split proposed",
            "blocked": "## Blocked by open items",
            "edit": "## Waiting on a body edit",
            "none": "## Nothing to do",
        }
    )
    refine_item_line: str = "- #{number} {title}"
    refine_refined_line: str = "- #{number} {title} (refined in this round)"
    refine_detail_line: str = "  - {detail}"
    refine_failed_heading: str = "## Failed Items"
    refine_failed_line: str = (
        "- #{number} {title}: skipped, its model call failed ({error}, {violations} schema "
        "violation(s))"
    )
    refine_failed: str = (
        "the model call failed for {count} item(s), and refine skipped them: {items}"
    )
    refine_failed_item: str = "#{number} ({error}, {violations} schema violation(s))"
    # `devops roadmap alternatives` (#2650).
    alternatives_title: str = "# Alternatives check for {repo}"
    alternatives_off: str = "The check is off: {reason}."
    alternatives_none: str = "No items to check."
    alternatives_checked_heading: str = "## Checked"
    alternatives_check_line: str = "- #{number} {title}: {verdict}"
    alternatives_current_heading: str = "## Checked lately"
    alternatives_current_line: str = "- #{number} {title}: checked on {date}, the text is unchanged"
    alternatives_skipped_heading: str = "## Skipped"
    alternatives_skipped_line: str = "- #{number} {title}: skipped, {reason}"
    alternatives_applied: str = "Checked {count} item(s) for open alternatives."
    alternatives_failed: str = (
        "the check failed for {count} item(s), and the others were written: {items}"
    )
    alternatives_failed_item: str = "#{number} ({reason})"
    alternatives_reason_stopped: str = "the model's run stopped ({reason})"
    alternatives_reason_error: str = "the model call failed ({error})"
    alternatives_reason_url: str = "the reply cites a URL that no tool returned: {url}"
    alternatives_reason_no_facts: str = "the reply names a tool whose facts no tool read: {url}"
    alternatives_reason_no_tool: str = "the reply gives the verdict {verdict} with no tool"
    alternatives_reason_not_applicable: str = (
        "the reply gives the verdict not-applicable after a tool ran"
    )
    alternatives_reason_markers: str = "the body holds a marker of the check with no partner"
    # What the tools of the check answer.
    alternatives_search_limit: str = "The search limit for this item is reached."
    alternatives_fact_limit: str = "The fact read limit for this item is reached."
    alternatives_bad_repository: str = "Give the repository as owner/name."
    alternatives_bad_package: str = "Give the package name as PyPI spells it."
    alternatives_no_repository: str = "GitHub has no repository {name}."
    alternatives_no_package: str = "PyPI has no package {name}."
    alternatives_read_failed: str = "The read failed: {error}."
    alternatives_fact_license: str = "License: {license}"
    alternatives_fact_push: str = "Last push: {date}"
    alternatives_fact_archived: str = "Archived: {answer}"
    alternatives_fact_stars: str = "Stars: {stars}"
    alternatives_fact_release: str = "Latest release: {release}"
    alternatives_fact_version: str = "Latest version: {version}"
    alternatives_fact_upload: str = "Latest upload: {date}"
    alternatives_not_stated: str = "not stated"
    alternatives_never: str = "never"
    alternatives_no_release: str = "none"
    alternatives_yes: str = "yes"
    alternatives_no: str = "no"
    # The comment and the body block the check writes.
    alternatives_comment_heading: str = "## Alternatives check: {verdict}"
    alternatives_comment_tool: str = "Tool: {name} ({url})"
    alternatives_comment_no_tool: str = "Tool: none found"
    alternatives_comment_license: str = "- License: {license}"
    alternatives_comment_activity: str = "- Last activity: {date}"
    alternatives_comment_maintained: str = "- Maintained: {answer}"
    alternatives_comment_covers: str = "Covers:"
    alternatives_comment_lacks: str = "Lacks:"
    alternatives_comment_queries: str = "Searches run:"
    alternatives_comment_sources: str = "Sources:"
    alternatives_comment_item: str = "- {text}"
    alternatives_comment_footer: str = (
        "Checked on {date}. A person decides what this means for the item. "
        "The check changes no label and closes no issue."
    )
    alternatives_block_verdict: str = "Alternatives check of {date}: {verdict}."
    alternatives_block_tool: str = (
        "Tool: {name} ({url}), {license}, last activity {date}, {maintained}."
    )
    alternatives_block_no_tool: str = "Tool: none found."
    alternatives_maintained: str = "maintained"
    alternatives_not_maintained: str = "not maintained"
    # `devops roadmap implement` (#2664): the refusals of a step, and why a step stops.
    implement_not_item: str = "#{number} is not an item of the roadmap."
    implement_no_change: str = "The checkout has no change folder that matches {pattern}."
    implement_many_changes: str = (
        "The checkout has more than one change folder that matches {pattern}: {names}."
    )
    implement_no_group: str = "The change {change} has no group {group}. Its groups are {groups}."
    implement_duplicate_group: str = (
        "The tasks.md of the change {change} has two groups numbered {group}."
    )
    implement_dirty: str = (
        "The checkout {path} has uncommitted changes. A step resets the checkout when it fails. "
        "Commit or discard the changes first."
    )
    implement_over_window: str = (
        "The inputs of the step measure {measured} tokens. The limit is {limit} tokens: the "
        "window of {window} tokens minus {reserve} tokens for the turns of the run."
    )
    implement_git_failed: str = "git {command} failed.\n{output}"
    implement_fix_title: str = "Make check {check} pass"
    implement_fix_task: str = "[ ] Make check `{check}` pass"
    implement_stop_unticked: str = "A task of the group is not ticked: {task}"
    implement_stop_tick_turn_changed: str = (
        "The extra turn for the ticks changed files other than the tasks file: {paths}."
    )
    implement_stop_repair_turn_changed: str = (
        "The extra turn for the static check changed files that the step had not changed: {paths}."
    )
    implement_paths_more: str = " and {count} more"
    implement_model_call_model: str = "model {model}"
    implement_model_call_status: str = "HTTP {status}, {model}"
    implement_model_call_body: str = "{detail}, body: {body}"
    implement_model_call_generation: str = (
        "The provider failed inside the stream. A known cause is that tool call parsing failed: "
        "Ollama refuses a tool call of the model when the XML of the call is not whole "
        "(ollama/ollama issue 18563)."
    )
    implement_stop_counts: str = "Refused commands: {refused}. Other retries: {retried}."
    implement_model_call_deadline: str = "{detail}, no complete reply in {seconds:g} seconds"
    implement_stop_capped: str = (
        "The model reply reached the output cap of {tokens} tokens, so the call ended."
    )
    implement_tool_other: str = "other"
    implement_refusal_replacement: str = "Instead of `{program}`: {replacement}."
    implement_refusal_allowed: str = (
        "These programs are allowed: {programs}. Run the commands of the project with `uv run`, "
        "for example `uv run devops ci test <file>`."
    )
    implement_refusal_operator: str = (
        "Run one command in each call. Do not chain commands. "
        "Do not use `cd`: every command runs in the checkout."
    )
    implement_tool_line: str = "Tool call: {tool}, {outcome}."
    implement_tool_line_program: str = "Tool call: {tool}, program {program}, {outcome}."
    implement_tool_started: str = "Tool call: {tool}, started: {command}"
    implement_tool_cut: str = " ..."
    implement_tool_reason: str = "{outcome} ({reason})"
    implement_tool_reason_path: str = "Path: {path}"
    implement_tool_path_hidden: str = "<path>"
    implement_stop_retries: str = "Last retries of {tool}: {reasons}"
    implement_stop_reasons_separator: str = " | "
    implement_tool_masked: str = "<masked>"
    implement_tick_turn: str = (
        "The checks of your group passed, but `{path}` still holds these tasks of your group "
        "unticked:\n\n{tasks}\n\nChange `- [ ]` to `- [x]` in front of each task whose work is "
        "done. Change nothing else in that file and change no other file. Then reply with one "
        "short message."
    )
    implement_repair_turn: str = (
        "A static check of your group failed:\n\n{failure}\n\nFix what the check reports. Change "
        "only the files that you changed.{ticks} Then reply with one short message."
    )
    implement_repair_turn_ticks: str = (
        " The file `{path}` also holds these tasks of your group unticked:\n\n{tasks}\n\n"
        "Change `- [ ]` to `- [x]` in front of each task whose work is done. Change nothing else "
        "in that file."
    )
    implement_restored_tasks: str = (
        "Restored the tasks.md of the change {change}. A step only ticks the tasks of its own "
        "group."
    )
    implement_stop_command_denied: str = (
        "The verification command {command} is not allowed. {program} is not one of: {allowed}."
    )
    implement_stop_command_unparsed: str = (
        "The verification command {command} is not a valid command line."
    )
    implement_stop_command_failed: str = "{command} exited with status {status}.\n{output}"
    implement_stop_command_timeout: str = "{command} ran out of time after {seconds} s."
    implement_formatted: str = "Formatted: {paths}"
    implement_stop_link: str = (
        "The agent made a symbolic link: {paths}. The step does not format a link."
    )
    implement_stop_no_change: str = "The agent changed no file."
    implement_stop_tests_lost: str = (
        "The agent removed tests that existed at the start of the step. "
        "A step may add tests. It may not remove or rename one.\n{files}"
    )
    implement_tests_lost_file: str = "{path}: {tests}"
    implement_stop_head_moved: str = (
        "The agent moved HEAD from {start} to {head}. A step makes the only commit."
    )
    implement_stop_commit_failed: str = "The commit failed.\n{output}"
    implement_title: str = "Implement step: item #{item}, group {group} ({title})"
    implement_labels: dict[str, str] = field(
        default_factory=lambda: {
            "status": "Status",
            "reason": "Reason",
            "commit": "Commit",
            "requests": "Model requests",
            "tool_calls": "Tool calls",
            "input_tokens": "Input tokens",
            "output_tokens": "Output tokens",
            "last_message": "Last message of the agent",
        }
    )
    # `devops roadmap eval implement` (#3030): the fixtures.
    eval_implement_no_fixtures: str = "No fixture folder at {path}."
    eval_implement_unreadable: str = "Fixture {name}: cannot read {file}: {reason}"
    eval_implement_invalid: str = "Fixture {name}: {problems}"
    eval_implement_name: str = (
        "Fixture {name}: the folder name must be the name in case.json, which is {given}."
    )
    eval_implement_no_group: str = "Fixture {name}: the plan has no group {group}."
    eval_implement_path_unnamed: str = (
        "Fixture {name}: `changes` lists {path}, and no code span of group {group} names it."
    )
    eval_implement_diff_missing: str = (
        "Fixture {name}: the result {result} names the diff results/{file}, which is missing."
    )
    eval_implement_command_property: str = (
        "the result {result} expects {prop} to fail, and only a tree can show that."
    )
    eval_implement_lost_form: str = "allow_lost_tests holds {entry}, which is not path::name."
    eval_implement_unknown: str = "No fixture is named {names}. The fixtures are: {known}."
    # The details of the properties.
    eval_implement_more: str = " and {count} more"
    eval_implement_lost_tests: str = "Lost tests: {names}."
    eval_implement_outside: str = "Paths outside the group: {names}."
    eval_implement_scratch: str = "Scratch files: {names}."
    eval_implement_unticked: str = "Tasks not ticked: {names}."
    eval_implement_group_gone: str = "The result has no group {group}."
    eval_implement_hunk: str = "A hunk of {path} does not match the plan."
    eval_implement_cut: str = "The diff is cut."
    eval_implement_unparsed: str = "The diff does not parse: {reason}"
    eval_implement_no_commands: str = "There is no command to run."
    eval_implement_no_tree: str = "The step stopped, so it left no tree: {reason}"
    # The report and the dry run.
    eval_implement_no_commit: str = (
        "Fixture {name}: this repository lacks the commit {sha}. Fetch the full history, then "
        "run again."
    )
    eval_implement_apply_failed: str = "The recorded diff does not apply to the base: {reason}"
    eval_implement_title: str = "Implement eval: {count} result(s), model {model}."
    eval_implement_title_check: str = "Implement eval of recorded results: {count} result(s)."
    eval_implement_running: str = "Running fixture {name} ({number} of {total})."
    eval_implement_head: str = "{name} / {result}: {status} (issue #{issue}, group {group})"
    eval_implement_reason: str = "  Reason: {reason}"
    eval_implement_cost: str = (
        "  Cost: {input_tokens} tokens in, {output_tokens} out, {requests} requests, "
        "{tool_calls} tool calls, {seconds:.1f} s."
    )
    eval_implement_property: str = "  {status:<7} {prop}{detail}"
    eval_implement_detail: str = ": {detail}"
    eval_implement_first_failed: str = "  First failed property: {prop}"
    eval_implement_as_recorded: str = "  As recorded: fails {fails}."
    eval_implement_not_recorded: str = (
        "  Not as recorded: expected to fail {expected}, failed {actual}."
    )
    eval_implement_nothing: str = "nothing"
    eval_implement_totals: str = "Properties: {passed} passed, {failed} failed, {skipped} skipped."
    eval_implement_differ: str = "{count} recorded result(s) differ from their record."
    eval_implement_saved: str = "Report: {path}"
    eval_implement_dry_title: str = (
        "Dry run: no request was made, nothing was cloned and no model ran. The steps are:"
    )
    eval_implement_dry_step: str = "- {name}: issue #{issue}, group {group}, base {sha}"
    eval_implement_dry_requests: str = "The model requests of a run:"
    eval_implement_model_target: str = "{model} for group {group} of item #{issue} (fixture {name})"
    implement_dry_run_reason: str = "Dry run: no request was made and nothing ran."
    implement_model_request: str = "model request"
    implement_model_target: str = "{model} for group {group} of item #{item}"
    implement_model_repeat: str = "up to {limit} times"
    # `devops roadmap implement` as a job (#2665): why it leaves an item out, and its plan.
    implement_left_not_ready: str = "Its Status is {status}, not Ready or Planned."
    implement_left_not_staged: str = (
        "It is neither Staged nor Planned: its record holds no staged branch or pull request, "
        "and {branch} holds no change folder for it."
    )
    implement_left_planned_branch: str = (
        "Its change folder `{folder}` gives the branch `{branch}`, which breaks the form "
        "<type>/<issue>-<slug>."
    )
    implement_left_all_ticked: str = (
        "Every task of its change `{folder}` is ticked, so no group is left to run."
    )
    implement_left_no_tasks: str = (
        "Its change `{folder}` has no readable tasks.md on {branch}: {reason}"
    )
    implement_left_stopped: str = (
        "A step stopped it at {stopped}. A person fixes the cause and comments `implement: retry`."
    )
    implement_left_author: str = (
        "Its author is {association}, not the owner, a member or a collaborator."
    )
    implement_left_no_app: str = (
        "No GitHub App slug is set in service.github_app.slug, so the author of a commit "
        "cannot be judged."
    )
    implement_left_no_branch: str = "Its staged branch `{branch}` is not on origin."
    implement_left_foreign: str = "Its branch has a commit by {author}, not by {bot}."
    implement_left_pull: str = "Its pull request #{pull} is not an open draft."
    implement_job_title: str = "# Implement plan for {repo}"
    implement_job_nothing: str = "No item to implement."
    implement_job_heading_ready: str = "## To implement"
    implement_job_heading_left: str = "## Left out"
    implement_job_ready_line: str = (
        "- #{number} {title}: branch `{branch}`, pull request #{pull}{retry}"
    )
    implement_job_planned_line: str = (
        "- #{number} {title}: Planned, new branch `{branch}` and a new pull request{retry}"
    )
    implement_job_retry_note: str = " (a retry: the stop on record is cleared first)"
    implement_job_left_line: str = "- #{number} {title}: {reason}"
    implement_hardening_failed: str = (
        "The implement job could not make its process unreadable by its own shell "
        "(prctl PR_SET_DUMPABLE): {reason}. It runs no step."
    )
    implement_job_token_not_app: str = (
        "The implement job runs only as the GitHub App, whose installation token a setting can "
        "limit to one repository. This process does not hold the App's private key. It ran no "
        "step."
    )
    implement_job_token_scope_refused: str = (
        "The implement job for {repo} needs a token for that one repository. Set "
        "service.github_app.token_repository to {repo}; it is now {scoped}. Without it the token "
        "covers every repository of the installation. This process ran no step."
    )
    implement_leftover_processes: str = (
        "A process that the agent's shell started is still alive after the step: {names}. The job "
        "runs no program with the GitHub token while such a process lives, so it stops the item."
    )
    implement_job_runner_refused: str = (
        "The implement job runs a step only in a runner pod. Set roadmap.implement.in_runner to "
        "true there. The shell of the agent is no security boundary, so the runner is the "
        "sandbox, with a narrow token and no other credential. This process ran no step."
    )
    implement_outside_why_options: str = (
        "Outside a runner, --confirm starts a runner Job for one item. It cannot pass {options}."
    )
    implement_outside_why_item: str = (
        "Outside a runner, --confirm starts a runner Job for one item, and needs --item <number>."
    )
    implement_outside_refused: str = (
        "{why} A step runs only when roadmap.implement.in_runner is true, which only the pod of "
        "a runner Job sets. To run the job with other options, put them after the `--` of this "
        "command: {command} <options> --confirm"
    )
    implement_outside_not_item: str = "Issue #{number} is not an item of the roadmap."
    implement_outside_closed: str = "Issue #{number} is closed."
    implement_outside_claimed: str = (
        "Item #{number} is claimed by {owner}. The job takes no item that an agent or a person "
        "claimed. Release it first: devops roadmap release {number} --confirm"
    )
    implement_outside_status: str = (
        "Item #{number} has the Status {status}. A runner Job takes an item that is Ready or "
        "Planned."
    )
    implement_job_applied: str = "Took {ready} item(s) to a ready pull request, stopped {stopped}."
    implement_job_yielded: str = "Left {yielded} item(s) to the owner that claimed them."
    implement_round_left: str = "Left #{number}: an agent or a person claimed it since the plan."
    implement_boundary_group: str = "the start of group {group}"
    implement_boundary_end: str = "the end of the last group"
    implement_boundary_stop: str = "the stop of {step}"
    implement_comment_claimed: str = (
        "{marker}\nThe job ended at {boundary}: {owner} claimed the item. It pushed nothing and "
        "opened no pull request. The groups that passed stay out of the branch. To give the item "
        "back to the Service, release it and set its Status to Ready."
    )
    implement_job_failed_item: str = "#{number} ({error}{reason})"
    implement_job_failed: str = "{count} item(s) failed: {items}"
    implement_step_group: str = "group {group}"
    implement_step_fix: str = "fix"
    implement_step_names: dict[str, str] = field(
        default_factory=lambda: {
            "rebase": "rebase",
            "docs": "docs",
            "archive": "archive",
            "push": "push",
            "pull_request": "pull request",
            "checks": "checks",
            "ready": "ready",
            "commit": "commit",
        }
    )
    implement_stop_rebase: str = "The rebase onto origin/{branch} stopped.\n{output}"
    implement_stop_abort_failed: str = "\nThe abort of the rebase failed too.\n{output}"
    implement_stop_program_failed: str = "{command} exited with status {status}.\n{output}"
    implement_stop_program_timeout: str = "{command} ran out of time after {seconds} s."
    implement_stop_checks_timeout: str = (
        "The checks of the pull request did not finish in {seconds} s."
    )
    implement_stop_old_head: str = (
        "GitHub did not show the commit {head} as the head of the pull request."
    )
    implement_stop_check_failed: str = "The check {name} failed."
    implement_stop_checks_unread: str = "GitHub could not say whether the checks passed."
    implement_stop_threads: str = "The pull request has {count} unresolved review thread(s)."
    implement_stop_conflict: str = "The pull request has a merge conflict with the default branch."
    implement_stop_merged: str = "The pull request was merged or closed while the job ran."
    implement_stop_ready_failed: str = "`gh pr ready` failed.\n{output}"
    implement_stop_error: str = "{error}: {message}"
    implement_stop_push_failed: str = "\nThe push of the commits that passed failed too.\n{output}"
    implement_comment_stopped: str = (
        "{marker}\nStopped at {step}.\n\nReason:\n\n{reason}\n\nLast message of the agent: "
        "{last}{diff}\n\nThe item is Blocked, and the job will not run it. Fix the cause. "
        "Then comment `implement: retry`. The Service also clears the stop one time when a new "
        "runner image rolls out.{note}"
    )
    implement_comment_last_none: str = "none."
    implement_comment_diff: str = (
        "\n\nThe job discarded this work.{cut} Read it before you retry:\n\n"
        "{fence}diff\n{diff}\n{fence}"
    )
    implement_comment_diff_cut: str = " The diff is cut to {limit} characters."
    implement_job_report: str = (
        "{marker}\nThe runner Job {name} ended: {state}.{digest}\n\n"
        "The last lines of its log:\n\n{log}"
    )
    implement_job_report_gone: str = (
        "{marker}\nThe runner Job {name} no longer exists, so it has no state and no log.{digest}"
    )
    implement_job_report_digest: str = "\nImage digest: {digest}"
    implement_job_report_no_log: str = "    (no log: the Job has no pod)"
    implement_job_report_stopped: str = (
        "\n\nThe Job left this item without a result. The item is Blocked, and the job "
        "will not run it. Fix the cause. Then comment `implement: retry`. The Service also "
        "clears the stop one time when a new runner image rolls out."
    )
    stop_clear_retry: str = (
        "{marker}\nCleared the stop at {stopped} by the rule `{rule}`: a person commented "
        "`implement: retry`. The item is {status} again, and the Service takes it in the next "
        "round."
    )
    stop_clear_digest: str = (
        "{marker}\nCleared the stop at {stopped} by the rule `{rule}`: the runner image changed "
        "since the stop, from {old} to {new}. The item is {status} again, and the Service takes "
        "it in the next round. The Service clears a stop one time for each runner image. A new "
        "stop on this image waits for a comment `implement: retry`."
    )
    implement_comment_finished: str = (
        "{marker}\nPull request #{pull} is ready for review. The checks passed.\n\n"
        "Spend: {requests} model requests, {input_tokens} input tokens, {output_tokens} output "
        "tokens."
    )
    implement_pull_comment: str = "{marker}\nThe steps of the job:\n\n{lines}"
    implement_pull_comment_line: str = (
        "- {step} ({title}): {status}, {requests} model requests{commit}"
    )
    implement_pull_comment_commit: str = ", commit `{commit}`"
    implement_pull_body: str = (
        "Closes #{number}\n\n{why}\n\nChange: `openspec/changes/archive/{archived}/`"
    )
    implement_pull_body_draft: str = (
        "Work on #{number}. The job closes the issue in the body when it finishes."
    )
    implement_stop_draft_failed: str = (
        "GitHub did not open the draft pull request of `{branch}`: {output}. The job removed the "
        "branch from origin."
    )
    implement_step_needs_item: str = "A step needs --item with --group."
    implement_step_job_options: str = (
        "--filter, --plan, --confirm and --why are options of the job. With --group, the command runs "
        "one step and takes only --item, --source, --format and --dry-run. To run the job for "
        "one item from a workstation, drop --group: devops roadmap implement --item <n> "
        "--confirm starts a runner Job."
    )
    implement_job_plain_note: str = (
        "Implement without a mode flag runs as --plan: it reads GitHub and git, and writes "
        "nothing. --dry-run makes no request."
    )
    # `devops roadmap stage` (#2654): the filter, and why the job leaves an item out.
    stage_filter_family: str = (
        "'{option}' is not a filter entry: '{family}' is not a label family to filter on. "
        "Use one of: {families}."
    )
    stage_filter_form: str = "'{option}' is not in the form family=value."
    stage_status_none: str = "none"
    stage_left_not_ready: str = "Status {status}: the stage job takes only Ready items."
    stage_left_needs_split: str = (
        "The item has the label needs-split. Refine proposed a split, and a person makes it first."
    )
    stage_left_tracker: str = (
        "The item is a tracker: it has sub-issues or the label type/epic. Its sub-issues deliver "
        "it, so it gets no plan of its own."
    )
    stage_left_author: str = (
        "The author's association with the repository is {association}. The model reads the "
        "body, so the stage job takes only the items that the owner, a member or a collaborator "
        "opened."
    )
    stage_left_dependency: str = "The item depends on the open issue {issues}."
    stage_left_title_type: str = (
        "The title has no Conventional Commit type, so the branch has no type."
    )
    stage_left_title_slug: str = "The summary of the title has no word for the branch name."
    stage_left_recorded_split: str = (
        "An earlier run stopped on a task group over the budget: {detail}. A person decides, or "
        "runs the job with --item {number}."
    )
    stage_left_secret: str = (
        "The title or the body looks like a secret, so the model does not read it."
    )
    stage_left_planned: str = "Its plan is on {branch}: the change folder `{folder}` is there."
    stage_left_archived: str = "Its change is archived on {branch}: the folder `{folder}` is there."
    # The files of the change that the stage job writes, and what its checks find wrong (#2654).
    stage_invalid: str = "The change fails its checks, also after a second try: {problem}"
    stage_closing: str = (
        "The title or the body of the pull request has the closing keyword {keyword} before an "
        "issue reference. A pull request that plans an item closes no issue."
    )
    stage_validate_unreadable: str = (
        "OpenSpec exited with 0 and printed no report that the stage job can read."
    )
    stage_secret: str = "The reply has text that looks like a secret, in {path}."
    stage_violations: str = "{count} schema violation(s)"
    git_failed: str = "`git {command}` failed: {reason}"
    # The comments of the stage job; each starts with its marker.
    stage_comment_staged: str = (
        "{marker}\nStaged: branch `{branch}`, draft pull request #{pull}. The pull request "
        "plans the item and closes no issue.\n\nThe task groups, with the tokens of the inputs "
        "of each step, for a budget of {budget} tokens:\n\n{groups}{notes}"
    )
    stage_comment_group: str = "{index}. {title}: {tokens} tokens"
    stage_comment_not_validated: str = (
        "\n\nThe `openspec` binary was not on PATH, so `openspec validate` did not run. The "
        "OpenSpec gate of CI judges the change."
    )
    stage_comment_over_budget: str = (
        '{marker}\nThe stage job stopped. The inputs of the step of the task group "{title}" '
        "hold {tokens} tokens, over the budget of {budget} tokens, also after the model split "
        "the groups once. A person decides how to split the item. The job stages the item again "
        "when a person runs it with --item {number}.\n\nThe task groups:\n\n{groups}"
    )
    stage_split_record: str = "{title} ({tokens} tokens)"
    stage_kept_reason: str = (
        "The branch holds {count} commit(s) by another author past the default branch, so the "
        "job keeps the branch and its draft."
    )
    # The report of `devops roadmap stage`.
    stage_title: str = "# Stage plan for {repo}"
    stage_budget: str = "The budget of one step is {budget} tokens."
    stage_nothing: str = "No item to stage."
    stage_heading_ready: str = "## To stage"
    stage_heading_over: str = "## Stopped: a task group is over the budget"
    stage_heading_left: str = "## Left out"
    stage_heading_failed: str = "## Failed"
    stage_heading_removals: str = "## Staged branches to remove"
    stage_heading_kept: str = "## Staged branches kept"
    stage_ready_line: str = (
        "- #{number} {title}: branch `{branch}`, {count} task group(s), the largest {largest} "
        "tokens{note}"
    )
    stage_unvalidated: str = ", `openspec validate` did not run"
    stage_over_line: str = '- #{number} {title}: the task group "{group}" holds {tokens} tokens'
    stage_left_line: str = "- #{number} {title}: {reason}"
    stage_failed_line: str = "- #{number} {title}: {error}{reason}"
    stage_removal_line: str = "- #{number}: `{branch}`{note}"
    stage_removal_gone: str = " is gone, and the job clears the record"
    stage_kept_line: str = "- #{number}: `{branch}`: {reason}"
    stage_applied: str = (
        "Staged {staged} item(s), stopped {stopped} on the budget, removed {removed} staged "
        "branch(es)."
    )
    stage_failed: str = "the stage job failed for {count} item(s): {items}"
    stage_failed_item: str = "#{number} ({error}{reason})"
    stage_ready_failed: str = "the stage_ready row failed for {count} pull request(s): {items}"
    status_sync_failed: str = "the Status of {count} item(s) could not be set: {items}"
    stage_plain_note: str = (
        "Stage without a mode flag runs as --plan: it reads GitHub and calls the model, and "
        "writes nothing. --dry-run makes no request."
    )
    # The requests of a stage run, as a dry run lists them.
    stage_requests: dict[str, str] = field(
        default_factory=lambda: {
            "update_clone": "update the model clone of the repository",
            "remote_heads": "the branches of origin",
            "fetch_default": "fetch the default branch, to read its plans",
            "default_plans": "the change folders of the default branch",
            "tracked_files": "the tracked files of the clone, to check the paths of each plan",
            "model_change": "the analysis model plans the change of the item",
            "model_split": "the analysis model splits the task groups over the budget",
            "model_correction": "the analysis model corrects a change that fails its checks",
            "validate": "validate the change with OpenSpec in a scratch directory",
            "fetch_branch": "the staged branch of a closed item",
            "worktree": "the worktree of the item's branch at the fetched default branch",
            "commit": "commit the change as the identity of the session",
            "push": "push the branch of the item",
            "pull": "open the draft pull request of the item",
            "delete_failed": "delete the pushed branch when the pull request cannot open",
            "close_pull": "close the draft pull request of a closed item",
            "delete_branch": "delete the staged branch of a closed item",
        }
    )
    stage_request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "tracked_files": "the filter names an item",
            "model_split": "a task group is over the budget",
            "model_correction": "the change fails its checks",
            "validate": "the openspec binary is on PATH",
            "delete_failed": "GitHub refuses the pull request",
            "close_pull": "only the identity of the session wrote to the branch",
            "delete_branch": "only the identity of the session wrote to the branch",
        }
    )
    implement_requests: dict[str, str] = field(
        default_factory=lambda: {
            "update_clone": "update the model clone of the repository",
            "remote_heads": "the branches of origin",
            "fetch_default": "fetch the default branch, to read its plans",
            "default_plans": "the change folders of the default branch",
            "planned_tasks": "the tasks of the change that the default branch holds",
            "fetch_branch": "the staged branch of an item",
            "authors": "the authors of the commits of the staged branch",
            "pull_status": "the state of the draft pull request of the item",
            "worktree": "the worktree on the staged branch, which the job takes over",
            "worktree_new": "the worktree on a new branch at the fetched default branch",
            "rebase": "rebase the staged branch onto the fetched default branch",
            "model_step": "the implement model runs one task group",
            "commit": "commit the files of the task group",
            "docs": "regenerate the documentation of the change",
            "archive": "archive the change",
            "push": "push the branch with a lease on its remote tip",
            "push_new": "push the new branch, once it holds a commit past the default branch",
            "create_pull": "open the draft pull request of the new branch",
            "body": "set the title and the body of the pull request to close the issue",
            "pull_comment": "comment the outcome of each step on the pull request",
            "run_log": "read the log of the failed check",
            "model_fix": "the implement model fixes the failed check, once",
            "watch": "read the pull request and its checks until they settle",
            "ready": "mark the pull request ready for review",
            "remove_worktree": "remove the worktree and the local branch",
        }
    )
    implement_request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "comments": "the item holds a stop",
            "planned": (
                "the item is Planned: its plan is on the default branch and its branch is gone"
            ),
            "staged": "the item is Staged: its branch is on origin",
            "clear_stop": "a retry comment clears the stop",
            "docs_commit": "the documentation changes",
            "run_log": "a check fails",
            "model_fix": "a check fails, for the first time",
            "ready": "the checks pass",
            "stop": "a step stops the item",
        }
    )
    stage_none: str = "None."
    stage_fits_one_pr: str = "The change fits one pull request."
    stage_pending_review: str = (
        "Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD)."
    )
    stage_bad_path: str = "'{path}' is not a path inside the repository."
    stage_bad_capability: str = (
        "'{capability}' is not a name. Use lowercase letters and digits joined by single hyphens."
    )
    stage_problem_purpose: str = (
        "The capability {capability} is not in openspec/specs/, so its entry needs a purpose of "
        "at least {count} characters."
    )
    stage_problem_modified: str = (
        "The capability {capability} is not in openspec/specs/, so it has no requirement to "
        "modify. Add the requirements instead."
    )
    stage_problem_keyword: str = "The requirement {requirement} does not say SHALL or MUST."
    stage_problem_skip_with_specs: str = "skip_specs is true, and the reply still gives specs."
    stage_problem_no_specs: str = "skip_specs is false, and the reply gives no spec delta."
    stage_problem_path: str = (
        "Group {group} names `{path}` in {place}. The staged commit has no such file, and no "
        "group up to group {group} creates it. {hint} Name a file that exists, or make the group "
        "that creates it list it in `creates`."
    )
    stage_path_same_name: str = "These files have the same name: {names}."
    stage_path_no_same_name: str = "No file has this name."
    stage_path_places: dict[str, str] = field(
        default_factory=lambda: {
            "reads": "`reads`",
            "changes": "`changes`",
            "task": "a task",
            "verify": "`verify`",
        }
    )
    stage_impact_line: str = "{kind}: {paths}"
    stage_impact_code: str = "Code"
    stage_impact_documents: str = "Documents"
    stage_impact_tests: str = "Tests"
    stage_group_files: str = "Reads: {reads}. Changes: {changes}."
    # The empty value of `reads` ends in no stop of its own: `stage_group_files` ends the sentence.
    stage_group_no_reads: str = "none"
    stage_group_new: str = " (new)"
    stage_blank_text: str = "A task text holds only full stops and spaces."
    stage_bad_creates: str = "'{path}' is in creates, and it is not in changes."
    stage_task_test: str = "{test}, and verify that `{verify}` fails on the base"
    stage_task_pass: str = "{work}, and verify that `{verify}` passes"
    stage_task_process: str = "{work}, and run this check by hand: {process}"
    stage_task_documents: str = (
        "{work}, run `{command}`, and verify that `uv run devops ci docs` passes"
    )
    stage_kind_no_test: str = (
        "The group '{title}' has the kind behavior, and it has no test. "
        "Give it the failing test to write first."
    )
    stage_kind_no_verify: str = (
        "The group '{title}' has the kind behavior, and it has no verify. "
        "Give it the command that runs its test."
    )
    stage_kind_behavior_process: str = (
        "The group '{title}' has the kind behavior, and it has a process. "
        "Its test is its check, so set process to null."
    )
    stage_kind_no_source: str = (
        "The group '{title}' has the kind behavior, and it changes no path under src/. "
        "Use the kind other, or add the path of the code that it changes."
    )
    stage_kind_other_test: str = (
        "The group '{title}' has the kind other, and it has a test. "
        "A group of this kind has no test, so set test to null."
    )
    stage_kind_no_check: str = (
        "The group '{title}' has the kind other, and it has neither verify nor process. "
        "Give it the command or the steps that prove it."
    )
    stage_kind_two_checks: str = (
        "The group '{title}' has the kind other, and it has both verify and process. "
        "Keep one of them."
    )
    stage_title_lead: str = "plan #{number} "
    stage_pull_request_body: str = (
        "Plans #{number}\n\n{body}\n\nChange: `openspec/changes/{change}/`"
    )
    # The dry runs of `devops roadmap` (#412, #1125): the requests a run makes, none made.
    plan_dry_run: str = (
        "Dry run: no request was made. A run makes these requests, in order; a value in "
        "<angle brackets> comes from an earlier read, a step with a condition runs only when it "
        "holds, and a step repeated runs as often as it says."
    )
    plan_dry_run_writes: str = "With --confirm, after the reads and before the last request:"
    plan_dry_run_title: str = "# devops roadmap {job} for {repo}"
    plan_dry_run_notes: tuple[str, ...] = (
        "Pacing a request, whether gh runs it or the GitHub session sends it, may read "
        "`gh api rate_limit`; that read costs no quota.",
    )
    plan_modes_exclusive: str = "Pass one of {modes}, not more."
    # `devops roadmap inbox` (#2915).
    inbox_title: str = "Waiting for a person in {repo}. The age is the time since the last update."
    inbox_empty: str = "Nothing waits for a person in {repo}."
    inbox_footer: str = (
        "Not listed: an image digest that is not rolled yet. "
        "Run `devops argo cd apps status devops` to read it."
    )
    inbox_headings: dict[str, str] = field(
        default_factory=lambda: {
            "plan": "Ready plan pull requests of the jobs (G1)",
            "implement": "Ready implementation pull requests of the jobs (G2)",
            "release": "The release pull request (G3)",
            "blocked": "Items in status/blocked",
            "claim": "Claims with no activity for {days} days",
            "labels": "Repository state that a person owns",
            "person": "Pull requests of people and agents",
        }
    )
    inbox_line: str = "  {number}  {age}  {subject}"
    inbox_clear: str = "      Clear it: {clear}"
    inbox_no_number: str = "-"
    inbox_no_age: str = "-"
    inbox_subjects: dict[str, str] = field(
        default_factory=lambda: {
            "pull": "{title}",
            "draft": "{title} (draft)",
            "stopped": "{title}: stopped at {step}",
            "blocked_by": "{title}: waits for {blockers}",
            "no_cause": "{title}: no cause is recorded",
            "claim": "{title} (claimed by {owner})",
            "labels": "{count} label(s) of {path} are missing or changed on GitHub: {names}",
            "more_labels": "{names}, and {more} more",
        }
    )
    inbox_clears: dict[str, str] = field(
        default_factory=lambda: {
            "plan": "Review it, then merge it (G1): {url}",
            "implement": "Review it, then merge it (G2): {url}",
            "release": "Review it, then merge it (G3): {url}",
            "person_ready": "Review it, then merge it (G2): {url}",
            "person_draft": (
                "Wait for the checks with `devops pr monitor {number} --repo {repo}`, "
                "then run `devops pr ready {number} --repo {repo}`."
            ),
            "stopped": "Fix the cause, then comment `{retry}` on #{number}.",
            "blocked": (
                "Fix the cause, then set the status by hand: `devops gh issues edit {number} "
                "--repo {repo} --add-label status/ready --remove-label status/blocked`."
            ),
            "claim": "devops roadmap release {number} --repo {repo} --confirm",
            "labels": "devops gh labels sync --repo {repo}",
        }
    )
    plan_repeat_page: str = "per page, while GitHub links a next one"
    plan_placeholders: dict[str, str] = field(
        default_factory=lambda: {
            "number": "<number>",
            "milestone": "<milestone>",
            "labels": "<the labels, the field's family replaced>",
            "record": "<the body, its job record block written>",
            "comment": "<comment>",
            "title": "<title>",
            "body": "<body>",
            "label": "<label>",
            "sub_issue_id": "<the child's REST id>",
            "node_id": "<node id>",
            "original_id": "<original node id>",
            "evidence": "<evidence>",
            "field": "<field>",
            "query": "<search query>",
            "repository": "<owner/name>",
            "package": "<package>",
            "item": "<item>",
            "blocker": "<blocking item>",
            "path": "<cited path>",
            "branch": "<branch>",
            "new_branch": "<new branch>",
            "change": "<change>",
            "pull": "<pull request>",
            "remote_tip": "<remote tip>",
        }
    )
    plan_targets: dict[str, str] = field(
        default_factory=lambda: {
            "file": "{path} at {ref}",
            "milestones": "every milestone",
            "issues": "the issues ({query})",
            "comments": "the comments on {subject}",
            "issue": "{subject}",
            "issue_now": (
                "{subject} as it is now: its labels and its job record; a write stops here when "
                "someone changed the field it writes since the run read it"
            ),
            "closures": "the closes and reopens on {subject}'s timeline",
            "advisory": "the advisory {subject} cites",
            "workflow_run": "the workflow run {subject} cites",
            "commit": "the commit {subject} cites",
            "path_change": "the newest commit on the default branch that changed {subject}",
            "open_pulls": "the open pull requests",
            "repository_labels": "the labels of the repository",
            "visibility": "whether the repository is private",
            "web_search": "a Firecrawl web search for {subject}",
            "repository_facts": "the repository {subject}",
            "latest_release": "the latest release of {subject}",
            "pypi_package": "the PyPI record of the package {subject}",
            "model_run": "the model's run on {subject}",
            "record": "the job record of {subject}, in its body",
            "set_field": "set {field} on {subject}: its labels and its job record, in one write",
            "body": "the body of {subject}, its job record kept",
            "comment": "comment on {subject}",
            "label": "label {subject}",
            "add_sub_issue": "add {subject} as a sub-issue of {parent}",
            "create_issue": "open an issue for {subject}",
            "close": "close {subject} with the reason {reason}",
        }
    )
    # The requests of a dry run that no `gh` command makes (#2650).
    plan_methods: dict[str, str] = field(
        default_factory=lambda: {
            "search": "Firecrawl search",
            "pypi": "PyPI read",
            "model": "model call",
        }
    )
    plan_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "posted": "the change posts a comment",
            "check_on": "the repository is public and a Firecrawl key is set",
            "issues_unread": "the run has not read every issue yet",
            "labels_differ": "the labels of the repository differ from .github/labels.yml",
            "still_waiting": "no comment follows refine's last comment on the waiting item",
            "capped": (
                "the cap on refine's comments leaves the item alone, and no earlier round "
                "recorded its newest comment"
            ),
        }
    )
    plan_repeat: dict[str, str] = field(
        default_factory=lambda: {
            "milestone": "for each open milestone, by due date and then by number",
            "item": "for each item the run judges or changes",
            "blocker": "for each open item a blocked item waits on",
            "block_path": "for each path the block of a waiting item cites, once a run",
            "evidence": "for each piece of evidence the model cites",
            "alternatives_item": "for each item the run checks, at most --limit",
            "search": "for each search the model asks for, at most {limit} for an item",
            "fact": "for each fact read the model asks for, at most {limit} for an item",
            "stage_item": "for each item the run stages, up to the limit",
            "stage_closed": "for each closed item whose record holds a staged branch",
            "implement_item": "for each item the run implements, up to the limit",
            "implement_group": "for each task group that has an unticked task",
        }
    )
    # `devops roadmap intake` (#742).
    intake_title: str = "# Intake for {repo}"
    intake_nothing: str = "No candidates."
    intake_issue: str = "#{number} {title}"
    intake_new: str = 'new candidate "{title}"'
    intake_not_candidate: str = (
        "- #{number}: not an open issue with no Priority, so intake leaves it alone."
    )
    intake_place_line: str = (
        "- {subject}: {type}, {priority}, Value {value}, Effort {effort}; {placement}"
    )
    intake_possible_duplicate_line: str = "  - possible duplicate: #{number}. {reason}"
    intake_possible_duplicate_field: str = "Possible duplicate"
    intake_possible_duplicate_value: str = "#{number}, which may ask for the same change"
    intake_possible_duplicate_reason: str = "{reason} A person closes one of the two if that is so."
    intake_duplicate_reason: str = (
        "The model names {change} as the change that both ask for. {reason}"
    )
    intake_related_line: str = "  - related: #{number}, which asks for a different change. {reason}"
    intake_related_field: str = "Related"
    intake_related_value: str = "#{number}, which asks for a different change"
    intake_skip_line: str = "- {subject}: skipped, nothing written: {reason}"
    intake_decision_lacks: str = "Intake cannot place {subject}: its decision has no {part}."
    intake_writes: str = "  - writes: {writes}"
    intake_note: str = "  - note: {note}"
    intake_write_file: str = "file the issue with {labels}"
    intake_write_sub_issue: str = "sub-issue of #{parent}"
    intake_no_labels: str = "no labels"
    intake_write_label: str = "label {label}"
    intake_write_field: str = "{field} {value}"
    intake_write_comment: str = "reason comment"
    intake_placement_backlog: str = "to the backlog: {reason}"
    intake_placement_kept: str = "kept in milestone {milestone}: {reason}"
    intake_reason_backlog: str = (
        "intake puts every new item in the backlog. A person plans the milestones."
    )
    intake_reason_person: str = "a person placed it in {milestone}, and that placement stands."
    intake_comment: str = "{marker}\nIntake placed this item {placement}\n\n{fields}"
    intake_comment_field: str = "- {field}: {value}. {reason}"
    intake_p0_granted: str = (
        "P0: the {kind} {value} is evidence GitHub confirms, from a trusted source."
    )
    intake_p0_refused: str = (
        "The {kind} {value} does not set P0: {why}. A person can set P0 with the label "
        "priority/p0-critical."
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
    intake_note_no_shared_change: str = (
        "the model named #{number} as the original but named no change that both items "
        "ask for, so the candidate is not a duplicate: intake places it and names #{number} as "
        "related."
    )
    intake_note_related_rejected: str = (
        "the model named #{number} as related, which is not one of the nearest items, so it "
        "was rejected."
    )
    intake_note_priority_capped: str = (
        "the model proposed {priority}, and it can propose only P1 to P3, so {capped} stands."
    )
    intake_note_evidence_dropped: str = (
        "the model's evidence ({kind} {value}) is not a GHSA ID, a run id or a commit SHA, so it "
        "was dropped."
    )
    intake_invalid: str = "the model's proposal is not valid: {problems}"
    intake_invalid_value: str = "{field} {value!r} is not one of {choices}"
    intake_preview: str = "Nothing was written. Run again with --confirm to make these writes."
    intake_plain_note: str = (
        "Intake without a mode flag runs as --plan: it reads GitHub and calls the model, and "
        "writes nothing. --dry-run makes no request."
    )
    intake_eval_title: str = (
        "# Intake duplicate evaluation: {cases} case(s), the analysis model {model} at {gateway}"
    )
    intake_eval_agree: str = "- agree: {name}: a person says {person}, intake says {intake}."
    intake_eval_disagree: str = (
        "- DISAGREE: {name}: a person says {person}, intake says {intake}.{reason}"
    )
    intake_eval_reason: str = " Intake's reason: {reason}"
    intake_eval_error: str = "- ERROR: {name}: {error}"
    intake_eval_agreed: str = "Agree: {agreed} of {cases} case(s)."
    intake_eval_score: str = (
        "Duplicate verdict: precision {true} of {said} ({precision}), recall {true} of "
        "{expected} ({recall}), {false} false duplicate(s)."
    )
    intake_eval_no_ratio: str = "none"
    intake_eval_failed: str = (
        "{failed} case(s) could not run. The score counts only the cases that ran."
    )
    intake_eval_dry_run: str = (
        "Dry run: no request was made. A run makes one analysis call to {gateway} for each "
        "case, one case at a time, and no embedding or GitHub request:"
    )
    intake_eval_dry_run_calls: str = "{calls} analysis call(s)."
    intake_eval_spent: str = (
        "Spent: {calls} analysis call(s) and {github} GitHub request(s). The run makes no "
        "embedding request."
    )
    intake_eval_labels_missing: str = (
        "This checkout has no {path}. The evaluation reads the type labels from it, as intake "
        "reads them from the repository. Run the command in a checkout that has the file."
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
        "With --confirm, after the reads, for each candidate intake places:"
    )
    intake_request_read: str = "read"
    intake_request_write: str = "write"
    intake_repeat_candidate: str = "for each candidate: an open issue with no Priority"
    intake_repeat_limited: str = (
        "for each of the {limit} oldest candidates: an open issue with no Priority"
    )
    intake_left: str = "Left for a later run, beyond the limit of {limit}: {left}."
    intake_placeholder_default_branch: str = "the default branch"
    intake_placeholder_each: str = "<the candidate>"
    intake_placeholder_filed: str = "<the filed issue>"
    intake_placeholder_fields: tuple[str, ...] = (
        "Status New",
        "Value <the proposed Value>",
        "Effort <the proposed Effort>",
    )
    intake_requests: dict[str, str] = field(
        default_factory=lambda: {
            "issues": (
                "every issue, open and closed, with its labels and job record: the candidates "
                "and the items"
            ),
            "closures": "the closes and reopens on {subject}'s timeline",
            "embed": (
                "every item, every issue closed as not planned and each candidate, in one call"
            ),
            "embed_new": (
                "every item, every issue closed as not planned, the open source/agent issues "
                "with no Priority and the new candidate, in one call"
            ),
            "labels": ".github/labels.yml at {ref}, for the type/* labels, once",
            "propose": "the proposal for {subject}",
            "evidence": "the evidence the model cites for {subject}",
            "comments": "the comments on {subject}, for intake's marker",
            "file": "file {subject}, with source/agent when an agent files it",
            "sub_issue": "link {subject} as a sub-issue of {parent}",
            "label": "label {subject} with its type/* label when it has none",
            "field": (
                "set {field} on {subject}: read the issue, then write its labels and its job "
                "record in one request"
            ),
            "comment": "the reason comment on {subject}",
            "priority": (
                "set Priority <the proposed Priority> on {subject}: read the issue, then write "
                "its labels and its job record in one request"
            ),
        }
    )
    intake_request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "candidate": "the run has a candidate",
            "embed": "the run has a candidate",
            "evidence": "the model cites any",
            "comments": "{subject} is placed",
            "file": "no open issue with no Priority holds its title and body",
            "sub_issue": "the candidate's source is an issue of the repository",
            "placed": "intake places {subject}",
            "field": "it has none",
            "comment": "intake's is not there",
            "priority": "it has none",
        }
    )
    intake_applied: str = "Intake placed {placed} item(s)."
    intake_filed: str = "Filed #{number}."
    intake_skipped: str = (
        "Intake skipped {name}: its writes failed, and the next run tries it again: {error}"
    )
    intake_failed: str = (
        "the writes failed for {count} candidate(s), and intake skipped them after writing the "
        "others; the next run tries them again: {items}"
    )
    intake_failed_item: str = "{name} ({error})"
    intake_failed_new: str = '"{title}"'
    triage_awaiting_intake: str = (
        "Issues awaiting intake get their type and Priority from `devops roadmap intake`."
    )
    intake_title_needs_body: str = "Pass --title and --body-file together."
    intake_secret: str = (
        "The candidate's {part} holds what looks like a secret, so intake sent it to no model "
        "and filed nothing. Remove it and run again."
    )
    intake_labels_unreadable: str = "{repo}'s {path} can't be read as label specs: {error}"
    intake_labels_missing: str = (
        "{repo} has no {path} at {ref}. Intake decides no candidate without it: the file must "
        "declare the type/* labels intake may assign."
    )
    intake_type_from_title: str = "The `{prefix}` prefix of the title gives the type."
    intake_scope_from_title: str = "The `({scope})` scope of the title gives the scope."
    intake_scope_undeclared: str = (
        "The title has the scope `{scope}`, and {path} declares no {label} label. Add the label "
        "to the file to give the scope to this item."
    )
    intake_labels_untyped: str = (
        "{repo}'s {path} at {ref} declares no type/* label other than type/epic. Intake decides "
        "no candidate without one: the file must declare the type/* labels intake may assign."
    )
    milestone_missing: str = "No milestone has the title or number {name!r}."
    milestone_title_taken: str = "Another milestone already has the title {title!r}."
    run_job_needs_clone: str = (
        "The roadmap {job} job reads its repository's clone and was given none: its row in the "
        "due table must set needs_clone."
    )
    run_intake_record_unreadable: str = (
        "The intake record {path} can't be read ({reason}), so intake does not run. Repair it, "
        "or remove it: the next intake then starts a new record and takes every candidate as "
        "never decided."
    )
    intake_issue_or_title: str = (
        "Pass --issue for existing issues, or --title and --body-file for a new candidate, "
        "not both."
    )


@dataclass(frozen=True)
class IssueMessages:
    """Messages of `devops gh issues`."""

    close_dry_run_title: str = "# devops gh issues close for {repo}"
    closed: str = "Closed #{number} as {reason}."
    close_empty_comment: str = (
        "The comment is empty. Give a file with the comment text, or no --comment-file."
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
            "edit": "set a planned field change on a card of board {board}",
        }
    )
    request_conditions: dict[str, str] = field(
        default_factory=lambda: {
            "not_found": "no board named {names} was found",
            "login_unread": ", and the login was not read earlier in the run",
        }
    )
    request_repeat_page: str = "per page after the first, while GraphQL reports a next page"
    request_repeat_edit: str = (
        "for each planned change, in order, until {limit} are made, GraphQL keeps fewer than "
        "{floor} points, or a write fails"
    )
    request_repeat_owner_fallback: str = (
        "once more with --owner @me when GitHub answers 'unknown owner type'"
    )
    request_repeat_listing: str = (
        "for each next page GitHub links, through the GitHub session, up to {max_pages} pages"
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


class SurveyMessages:
    survey_dependencies_title: str = "Pinned Runtime Dependencies Upstream Maintenance"
    survey_capabilities_title: str = "Outward Capability Comparison"
    candidate_emitted: str = (
        "Emitted capability gap candidate for {capability} (present in {tool})."
    )
    candidate_filed: str = "Filed roadmap candidate #{number} for {capability}."
    no_gaps_found: str = "No capability gaps detected."
    gaps_found: str = "Detected {count} capability gap(s) compared to external tools."


@dataclass(frozen=True)
class LanguageCatalog:
    persona_titles: PersonaTitles = field(default_factory=PersonaTitles)
    messages: GeneralMessages = field(default_factory=GeneralMessages)
    badges: BadgeMessages = field(default_factory=BadgeMessages)
    output: OutputMessages = field(default_factory=OutputMessages)
    review: ReviewMessages = field(default_factory=ReviewMessages)
    ai: AIMessages = field(default_factory=AIMessages)
    survey: SurveyMessages = field(default_factory=SurveyMessages)
    benchmark: BenchmarkMessages = field(default_factory=BenchmarkMessages)
    config: ConfigMessages = field(default_factory=ConfigMessages)
    install: InstallMessages = field(default_factory=InstallMessages)
    openspec: OpenSpecMessages = field(default_factory=OpenSpecMessages)
    branches: BranchMessages = field(default_factory=BranchMessages)
    workspace: WorkspaceMessages = field(default_factory=WorkspaceMessages)
    repos: RepoMessages = field(default_factory=RepoMessages)
    k8s: K8sMessages = field(default_factory=K8sMessages)
    analyze: AnalyzeMessages = field(default_factory=AnalyzeMessages)
    docs: DocsMessages = field(default_factory=DocsMessages)
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
    issues: IssueMessages = field(default_factory=IssueMessages)


MESSAGES = LanguageCatalog()
