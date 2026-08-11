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
    step1_metadata: str = "Step 1/4: Analyzing metadata across {count} segment(s)..."
    step2_segment: str = "Step 2/4: Reviewing {count} segment(s)..."
    step3_validate: str = "Step 3/4: Validating findings for {count} segment(s)..."
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


class LanguageCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    persona_titles: PersonaTitles = PersonaTitles()
    messages: GeneralMessages = GeneralMessages()
    review: ReviewMessages = ReviewMessages()
    ai: AIMessages = AIMessages()
    config: ConfigMessages = ConfigMessages()
    install: InstallMessages = InstallMessages()


MESSAGES = LanguageCatalog()
