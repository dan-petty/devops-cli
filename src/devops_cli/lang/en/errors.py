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
    registration_failed: str = "GitHub key registration failed: {exc}"


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
    cannot_write_outside: str = "Cannot write workspace file '{path}' outside boundary."


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
class ArgoErrorMessages:
    url_not_configured: str = "ArgoCD URL not configured. Run: devops config set argocd.url <url>"
    connect_failed: str = "Failed to connect to ArgoCD: {exc}"
    app_not_found: str = "Application '{name}' not found."


@dataclass(frozen=True)
class CIErrorMessages:
    python_version_fail: str = "Strict Python {required}+ requirement failed. Current: {current}"
    python_version_failed: str = "Strict Python {version}+ requirement failed. Current: {current}"
    checks_failed: str = "CI Quality Gate checks failed. Resolve errors before releasing."


@dataclass(frozen=True)
class DevcontainerErrorMessages:
    manifest_not_found: str = "DevContainer manifest not found: {path}"
    parse_failed: str = "Failed to parse DevContainer manifest JSON in {path}: {exc}"
    validation_failed: str = "DevContainer manifest validation failed for {path}:"
    no_devcontainer_found: str = "No devcontainer.json found: {path}"
    invalid_json: str = "Invalid JSON in {path}: {exc}"


@dataclass(frozen=True)
class DockerErrorMessages:
    cannot_connect: str = "Cannot connect to Docker: {exc}"
    invalid_image_name: str = "Invalid Docker image name format: '{image}'"
    push_failed: str = "Docker push failed: {error}"


@dataclass(frozen=True)
class GrafanaErrorMessages:
    url_not_configured: str = "Grafana URL not configured. Run: devops config set grafana.url <url>"
    invalid_uid: str = "Invalid Dashboard UID: alphanumeric, hyphens, and underscores only."
    invalid_output_path: str = "Invalid output path: path traversal not allowed."
    file_too_large: str = "File '{path}' exceeds maximum allowed size ({max_bytes} bytes)."
    parse_failed: str = "Failed to parse dashboard JSON file '{path}': {exc}"
    invalid_json_object: str = "Invalid dashboard JSON in '{path}': expected JSON object."
    sync_failed: str = "Failed to sync '{file}': {exc}"


@dataclass(frozen=True)
class MCPErrorMessages:
    invalid_transport: str = "Invalid transport '{transport}'. Choose 'stdio' or 'sse'."


@dataclass(frozen=True)
class ReleaseErrorMessages:
    branch_create_failed: str = "Failed to create release branch {branch}: {error}"
    version_mismatch: str = (
        "Version mismatch: pyproject.toml ({pyproject}) != src/devops_cli/__init__.py ({init})"
    )
    working_tree_dirty: str = (
        "Git working directory is dirty. Commit or stash changes before releasing."
    )
    docs_out_of_sync: str = "Documentation is out of sync. Run 'devops release prepare' or 'devops docs generate --sync-readme'"
    tag_create_failed: str = "Failed to create git tag {tag}: {error}"
    tag_push_failed: str = "Failed to push tag {tag} to origin: {error}"
    invalid_label: str = "Invalid label '{label}'."
    invalid_version_format: str = "Invalid semver version format: '{version}'."


@dataclass(frozen=True)
class TLSErrorMessages:
    cert_not_found: str = "Error: Certificate file not found: {path}"
    ca_not_found: str = "Error: CA certificate file not found: {path}"
    verification_failed: str = (
        "Verification Failed: [cyan]{cert}[/cyan] is invalid or not signed by [cyan]{ca}[/cyan]"
    )


@dataclass(frozen=True)
class PrometheusErrorMessages:
    url_not_configured: str = (
        "Prometheus URL not configured. Run: devops config set prometheus.url <url>"
    )
    expr_too_long: str = "PromQL expression exceeds maximum length of {max_len} characters."
    unexpected_content_type: str = "Unexpected Content-Type '{content_type}' from Prometheus API."
    query_failed: str = "Query failed: {error}"


@dataclass(frozen=True)
class RAGErrorMessages:
    cannot_connect: str = "Cannot connect to Qdrant at [bold]{url}[/bold]\nTip: Deploy or start Qdrant via 'devops k8s deploy-stack llm'"
    cannot_connect_store: str = "Cannot connect to Qdrant vector store at {url}"
    path_not_found: str = "Path not found: {path}"
    fetch_details_failed: str = "Could not fetch collection details: {exc}"


@dataclass(frozen=True)
class TfErrorMessages:
    binary_not_found: str = "Neither 'tofu' nor 'terraform' binary was found in PATH."
    unsupported_cloud_provider: str = (
        "Unsupported cloud provider '{provider}'. Supported providers: aws, azure, gcp"
    )


@dataclass(frozen=True)
class PRErrorMessages:
    list_failed: str = "Failed to list PRs: {error}"
    invalid_number: str = "Invalid PR number: {number}"


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
    argo: ArgoErrorMessages = field(default_factory=ArgoErrorMessages)
    ci: CIErrorMessages = field(default_factory=CIErrorMessages)
    devcontainer: DevcontainerErrorMessages = field(default_factory=DevcontainerErrorMessages)
    docker: DockerErrorMessages = field(default_factory=DockerErrorMessages)
    grafana: GrafanaErrorMessages = field(default_factory=GrafanaErrorMessages)
    mcp: MCPErrorMessages = field(default_factory=MCPErrorMessages)
    release: ReleaseErrorMessages = field(default_factory=ReleaseErrorMessages)
    tls: TLSErrorMessages = field(default_factory=TLSErrorMessages)
    prometheus: PrometheusErrorMessages = field(default_factory=PrometheusErrorMessages)
    rag: RAGErrorMessages = field(default_factory=RAGErrorMessages)
    tf: TfErrorMessages = field(default_factory=TfErrorMessages)
    pr: PRErrorMessages = field(default_factory=PRErrorMessages)


ERRORS = ErrorCatalog()
