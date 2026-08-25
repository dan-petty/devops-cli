"""Centralized error and warning messages catalog for devops-cli (English)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIErrorMessages:
    test_failed: str = "✗ Failed: {exc}"
    llm_unavailable_template_fallback: str = "LLM unavailable ({exc}), falling back to template."
    llm_failed_template_fallback: str = "LLM failed ({exc}), using template."
    empty_prompt: str = "Error: Prompt cannot be empty."
    provider_connection_error: str = "Could not connect to AI provider at {url}: {exc}"
    unsupported_provider: str = "Unsupported AI provider '{provider}'."


@dataclass(frozen=True)
class GitErrorMessages:
    git_diff_failed: str = "git diff failed: {error}"
    detect_branch_failed: str = (
        "Could not detect branch. Ensure command is run inside a valid git repo."
    )
    outside_boundary: str = "Error: Target path '{target}' is outside allowed boundaries."
    exceeds_max_size: str = "Error: Target file '{target}' exceeds maximum size ({max_mb}MB)."
    github_repo_parse_failed: str = "Could not parse GitHub repo owner/name from remote URL: {raw}"
    target_path_outside_repo: str = "Error: Target path '{dest}' is outside repository boundary."


@dataclass(frozen=True)
class ConfigErrorMessages:
    secret_storage_failed: str = "Failed to store secret in OS keyring: {exc}"
    invalid_setting_key: str = "Invalid setting key '{key}'."
    config_file_not_found: str = "Config file not found at '{path}'."


@dataclass(frozen=True)
class K8sErrorMessages:
    context_not_found: str = "Kubernetes context '{context}' was not found."
    resource_lookup_failed: str = "Failed to lookup Kubernetes {resource}: {exc}"
    port_forward_failed: str = "Port-forwarding to {service}:{port} failed: {exc}"


@dataclass(frozen=True)
class SSHErrorMessages:
    key_already_exists: str = "Key already exists: {key_path}"
    no_ssh_key_found: str = "No managed SSH key found. Run 'devops ssh generate' first."
    public_key_not_found: str = "Public key not found: {pub_path}"
    failed_to_register_key: str = "Failed to register key on GitHub: {error}"


@dataclass(frozen=True)
class WorkspaceErrorMessages:
    file_too_large: str = "Workspace file too large to load: {ws_file}. Using defaults."
    malformed: str = "Malformed workspace file structure: {ws_file}. Using defaults."
    corrupted: str = "Corrupted workspace file: {ws_file}. Using defaults."
    outside_roots: str = "Error: Cannot add path '{path}' outside allowed workspace roots."
    already_present: str = "Already in workspace: {path}"
    not_present: str = "Not found in workspace: {path}"
    repos_not_found: str = "Repos directory not found: {path}"
    file_not_found: str = "Workspace file not found: {ws_file}"


@dataclass(frozen=True)
class UVErrorMessages:
    no_version_provided: str = "No Python version provided and .python-version is missing."
    invalid_version_format: str = "Invalid Python version format: {version}"
    missing_command: str = "Missing command. Example: devops uv run -- pytest -q"


@dataclass(frozen=True)
class KustomizeErrorMessages:
    path_not_exists: str = "Path '{path}' does not exist."


@dataclass(frozen=True)
class ToolErrorMessages:
    download_failed: str = "Error downloading {name} from {url}: {exc}"
    tool_binary_not_found: str = "Required tool binary '{name}' was not found in PATH."
    access_denied_outside_workspace: str = "Access Denied: {path} is outside workspace."
    file_not_found: str = "File not found: {path}"
    error_reading_file: str = "Error reading file: {exc}"
    tool_execution_failed: str = "{tool} execution failed: {exc}"


@dataclass(frozen=True)
class ErrorCatalog:
    ai: AIErrorMessages = field(default_factory=AIErrorMessages)
    git: GitErrorMessages = field(default_factory=GitErrorMessages)
    config: ConfigErrorMessages = field(default_factory=ConfigErrorMessages)
    k8s: K8sErrorMessages = field(default_factory=K8sErrorMessages)
    ssh: SSHErrorMessages = field(default_factory=SSHErrorMessages)
    workspace: WorkspaceErrorMessages = field(default_factory=WorkspaceErrorMessages)
    uv: UVErrorMessages = field(default_factory=UVErrorMessages)
    kustomize: KustomizeErrorMessages = field(default_factory=KustomizeErrorMessages)
    tools: ToolErrorMessages = field(default_factory=ToolErrorMessages)


ERRORS = ErrorCatalog()
