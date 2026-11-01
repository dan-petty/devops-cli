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
    unknown_benchmark_type: str = "Unknown benchmark type '{value}': use one of {choices}."
    benchmark_corpus_conflict: str = (
        "--document and --code each choose the corpus the embedding benchmark ranks: pass one."
    )
    benchmark_server_url: str = "--servers entry {position} ({server}) is not an http or https URL."
    benchmark_no_code_queries: str = (
        "No code chunk under '{path}' has a symbol name to query by, so the benchmark has "
        "nothing to retrieve: point --code at a directory of source files."
    )


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
    github_unauthenticated: str = (
        "GitHub is not authenticated: `gh auth token` printed no token (exit status {status}). "
        "Run 'gh auth login', or set GH_TOKEN."
    )
    github_token_lookup_failed: str = (
        "GitHub is not authenticated: `gh auth token` could not run ({reason}). "
        "Check that gh is installed, on PATH and answering, then run 'gh auth login' or set GH_TOKEN."
    )
    github_token_lookup_not_found: str = "gh is not on PATH"
    github_token_lookup_timed_out: str = "no answer within {seconds:g} s"
    github_app_settings_missing: str = (
        "The environment holds {key_env}, so this process acts as a GitHub App, but these "
        "settings are not set: {settings}. Set them with 'devops config set'."
    )
    github_app_token_failed: str = (
        "GitHub App {login} has no installation token: {reason}. Check the App ID, the "
        "installation ID and the private key in {key_env}."
    )
    github_app_permissions_not_granted: str = (
        "{reason} The installation must grant each permission that the token asks for: "
        "{permissions}"
    )
    github_app_repository_not_granted: str = (
        "{reason} The installation must include repository {repository}, and grant each "
        "permission that the token asks for: {permissions}"
    )
    github_app_key_unreadable: str = "the private key is not an RSA private key in PEM form"
    github_app_answer_unreadable: str = "GitHub's answer holds no token and expiry time"


@dataclass(frozen=True)
class ConfigErrorMessages:
    secret_storage_failed: str = "Failed to store secret in OS keyring: {exc}"
    invalid_setting_key: str = "Invalid setting key '{key}'."
    config_file_not_found: str = "Config file not found at '{path}'."
    unknown_key: str = (
        "Unknown configuration key '{key}'{location}.{reason} Remove it with: {command}"
    )
    unknown_key_location: str = " at {path}:{line}"
    unknown_key_removed: str = " Release {release} removed it."
    unknown_key_serving: str = (
        " Per-model sampling and serving settings belong in a gateway deployment's "
        "litellm_params or the Ollama tag."
    )
    key_not_in_file: str = "The config file {path} does not hold the key '{key}'. Nothing changed."
    not_yaml: str = "Cannot load the settings: {path} is not valid YAML ({error_type}){location}."
    not_yaml_location: str = " at line {line}, column {column}"
    not_mapping: str = "Cannot load the settings: {path} does not hold a mapping of keys to values."


@dataclass(frozen=True)
class K8sErrorMessages:
    context_not_found: str = "Kubernetes context '{context}' was not found."
    resource_lookup_failed: str = "Failed to lookup Kubernetes {resource}: {exc}"
    port_forward_failed: str = "Port-forwarding to {service}:{port} failed: {exc}"
    volume_not_found: str = "PersistentVolume '{name}' not found."
    tunnel_host_unset: str = (
        "Set k8s.tunnel_host to the hostname of the Kubernetes API route, for example "
        "'devops config set k8s.tunnel_host k8s.example.com'."
    )
    tunnel_cloudflared_missing: str = (
        "cloudflared is not on PATH. Install it with 'devops install-tools --tool cloudflared'."
    )
    tunnel_login_failed: str = (
        "The Cloudflare Access login for {host} failed with exit code {code}."
    )
    tunnel_port_in_use: str = (
        "Another program listens on {listener}. Stop it, or give another port with --port."
    )
    tunnel_exited: str = (
        "cloudflared stopped with exit code {code} before {listener} accepted connections. Read "
        "its log: {log}"
    )
    tunnel_not_listening: str = (
        "{listener} did not accept connections in {seconds:g} s, so the forward was stopped. Read "
        "the cloudflared log: {log}"
    )
    tunnel_context_unread: str = (
        "The kubeconfig context {context} gives no cluster, user or CA data to copy."
    )
    volume_not_orphaned_phase: str = (
        "PersistentVolume '{name}' phase is '{phase}' (must be Released or Failed)."
    )
    volume_not_orphaned_claim: str = (
        "PersistentVolumeClaim '{namespace}/{claim}' referenced by '{name}' still exists."
    )
    volume_not_orphaned_mount: str = "Pod '{namespace}/{pod}' mounts volume '{name}'."
    volume_reclaim_non_interactive: str = (
        "Non-interactive session requires --yes to confirm PersistentVolume reclaim."
    )


@dataclass(frozen=True)
class SSHErrorMessages:
    key_already_exists: str = "Key already exists: {key_path}"
    public_key_not_found: str = "Public key not found: {pub_path}"
    failed_to_register_key: str = "Failed to register key on GitHub: {error}"
    registration_failed: str = "GitHub key registration failed: {exc}"


@dataclass(frozen=True)
class WorkspaceErrorMessages:
    file_too_large: str = (
        "Workspace file too large to load: {ws_file}. It was left unchanged; "
        "run 'devops workspace generate' to rebuild it."
    )
    malformed: str = (
        "Workspace file {ws_file} has no 'folders' list. It was left unchanged; "
        "fix it or run 'devops workspace generate' to rebuild it."
    )
    corrupted: str = (
        "Workspace file {ws_file} is not UTF-8 JSON; comments and trailing commas are not "
        "supported. It was left unchanged; fix it or run 'devops workspace generate' to "
        "rebuild it."
    )
    outside_roots: str = "Error: Cannot add path '{path}' outside allowed workspace roots."
    outside_boundary: str = "Cannot write workspace file '{path}' outside boundary."
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
    keyring_unavailable: str = (
        "No keyring in this container: DBUS_SESSION_BUS_ADDRESS is unset or "
        "gnome-keyring is not installed. Rebuild the devcontainer."
    )
    keyring_empty_password: str = (
        "Refusing an empty password: the keyring would store every secret in plain text."
    )
    keyring_password_mismatch: str = "Passwords do not match; the keyring was not created."
    keyring_wrong_password: str = (
        "Wrong password; the keyring is still locked. To reset the keyring, "
        "move {path} to a backup file and run 'devops devcontainer unlock-keyring'."
    )
    keyring_not_created: str = "The keyring could not be created or reached over D-Bus."


@dataclass(frozen=True)
class DockerErrorMessages:
    cannot_connect: str = "Cannot connect to Docker: {exc}"
    invalid_image_name: str = "Invalid Docker image name format: '{image}'"
    push_failed: str = "Docker push failed: {error}"
    podman_no_build_cache: str = "Podman keeps no BuildKit cache; its build layers are images, and `devops docker prune` removes the dangling ones."


@dataclass(frozen=True)
class GrafanaErrorMessages:
    url_not_configured: str = "Grafana URL not configured. Run: devops config set grafana.url <url>"
    invalid_uid: str = "Invalid Dashboard UID: alphanumeric, hyphens, and underscores only."
    invalid_output_path: str = "Invalid output path: path traversal not allowed."
    file_too_large: str = "File '{path}' exceeds maximum allowed size ({max_bytes} bytes)."
    parse_failed: str = "Failed to parse dashboard JSON file '{path}': {exc}"
    invalid_json_object: str = "Invalid dashboard JSON in '{path}': expected JSON object."
    sync_failed: str = "Failed to sync '{file}': {exc}"
    dashboards_not_found: str = "Dashboard path not found: {path}"


@dataclass(frozen=True)
class MCPErrorMessages:
    invalid_transport: str = "Invalid transport '{transport}'. Choose 'stdio' or 'sse'."
    hyphen_prefixed_argument: str = (
        "Invalid value for '{name}': must not start with a hyphen. "
        "Hyphen-prefixed values could be interpreted as flags by the underlying command."
    )
    integer_below_minimum: str = "Invalid value for '{name}': {value}. Must be >= {min_val}."
    integer_above_maximum: str = "Invalid value for '{name}': {value}. Must be <= {max_val}."
    unknown_provider: str = "Invalid value for 'provider': use one of {choices}."
    model_names_endpoint: str = (
        "Invalid value for 'models': an entry with '@' names the server that gets the "
        "requests of the benchmark, which only the command line may choose. "
        "Name each model alone; it runs on the configured servers."
    )
    conflicting_symbol_and_pattern: str = (
        "Cannot specify both 'symbol' and 'pattern'; provide one or the other."
    )
    security_sse_non_loopback: str = (
        "Refusing to bind SSE transport to non-loopback host '{host}' by default. "
        "Use allow_remote=True to permit external host binding."
    )


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
    invalid_promql: str = "Invalid PromQL expression: {errors}"
    unexpected_content_type: str = "Unexpected Content-Type '{content_type}' from Prometheus API."
    query_failed: str = "Query failed: {error}"


@dataclass(frozen=True)
class RAGErrorMessages:
    cannot_connect_store: str = "Cannot connect to Qdrant vector store at {url}"
    path_not_found: str = "Path not found: {path}"
    fetch_details_failed: str = "Could not fetch collection details: {exc}"
    embedding_failed: str = "Embedding model {model} produced no embeddings: {failures}"
    embedding_endpoint_status: str = "{endpoint} answered HTTP {status}: {body}"
    embedding_endpoint_malformed: str = (
        "{endpoint} returned {received} embeddings for {expected} texts"
    )
    embedding_endpoint_error: str = "{endpoint} failed: {error}"
    embedding_no_provider: str = (
        "Embedding model {model} has no provider: the embedding task's provider '{provider}' "
        "is not ollama, openai, copilot or gateway, and no Ollama URLs are set. "
        "Set ai.tasks.embedding.provider"
    )
    embedding_no_ollama_urls: str = (
        "Embedding model {model} has no Ollama URL: ai.provider is '{provider}' and "
        "ai.ollama_urls is empty. Set ai.ollama_urls"
    )
    batch_failed: str = "Failed to embed batch from '{first_file}' to '{last_file}': {error}"


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
    no_pr_for_branch: str = "No open pull request found for current branch '{branch}'."


@dataclass(frozen=True)
class DashboardErrorMessages:
    unknown_tab: str = "Unknown tab '{value}': use one of {choices}."


@dataclass(frozen=True)
class TestErrorMessages:
    k6_not_found: str = "k6 binary not found in PATH. Install k6 (e.g. apt install k6 or brew install k6) to run load tests."
    load_test_failed: str = "Load test failed with exit code {code}."


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
    tls: TLSErrorMessages = field(default_factory=TLSErrorMessages)
    prometheus: PrometheusErrorMessages = field(default_factory=PrometheusErrorMessages)
    rag: RAGErrorMessages = field(default_factory=RAGErrorMessages)
    tf: TfErrorMessages = field(default_factory=TfErrorMessages)
    pr: PRErrorMessages = field(default_factory=PRErrorMessages)
    test: TestErrorMessages = field(default_factory=TestErrorMessages)
    dashboard: DashboardErrorMessages = field(default_factory=DashboardErrorMessages)


ERRORS = ErrorCatalog()
