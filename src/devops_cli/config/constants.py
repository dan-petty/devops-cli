"""Non-configurable constants used across the CLI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

# ── Application & Configuration ───────────────────────────────────────────────
CONST_APP_NAME = "devops-cli"
CONST_HELP_OPTION_NAMES = ("-h", "--help")
CONST_CONFIG_DIR = Path.home() / ".config" / CONST_APP_NAME
CONST_CONFIG_PATH = CONST_CONFIG_DIR / "config.yaml"
CONST_KEYRING_SERVICE = CONST_APP_NAME
CONST_PROJECT_CONFIG_FILENAME = "config.yaml"
CONST_PROJECT_CONFIG_ENV = "DEVOPS_CLI_CONFIG"  # absolute path overrides CWD lookup
CONST_VSCODE_WORKSPACE_FILE = Path(".code-workspace")
CONST_VSCODE_CLI = "code"
CONST_AGENTS_MD_FILENAME = "AGENTS.md"
CONST_PYPROJECT_FILENAME = "pyproject.toml"
CONST_UV_LOCK_FILENAME = "uv.lock"
CONST_PRE_COMMIT_CONFIG_FILENAME = ".pre-commit-config.yaml"
CONST_CHANGELOG_FILENAME = "CHANGELOG.md"
CONST_README_FILENAME = "README.md"
CONST_INIT_PY_PATH = Path("src/devops_cli/__init__.py")
CONST_CONVENTIONAL_COMMIT_CATEGORIES: Final[dict[str, str]] = {
    "feat": "Added",
    "fix": "Fixed & Hardened",
    "sec": "Fixed & Hardened",
    "security": "Fixed & Hardened",
    "perf": "Changed & Improved",
    "refactor": "Changed & Improved",
    "docs": "Changed & Improved",
    "chore": "Changed & Improved",
    "ci": "Changed & Improved",
    "test": "Changed & Improved",
    "style": "Changed & Improved",
}
CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "Added",
    "Fixed & Hardened",
    "Changed & Improved",
    "Other Changes",
)
CONST_CURRENT_DIR = Path(".")
CONST_ROOT_DIR = Path("/")
CONST_SRC_DIR_NAME = "src"
CONST_DOCS_DIR_NAME = "docs"
CONST_DOCS_DIR_PATH = Path(CONST_DOCS_DIR_NAME)
CONST_TESTS_DIR_NAME = "tests"
CONST_TESTS_DIR_PATH = Path(CONST_TESTS_DIR_NAME)
CONST_VSCODE_DIR_NAME = ".vscode"
CONST_MCP_JSON_NAME = "mcp.json"
CONST_MCP_RESOURCE_SCHEME = "resource://"
CONST_MCP_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "ai",
        "argo",
        "benchmark",
        "config",
        "docker",
        "github",
        "grafana",
        "k8s",
        "prometheus",
        "review",
        "sandbox",
        "scan",
        "secrets",
        "ssh",
        "telemetry",
        "tf",
        "tls",
        "valkey",
        "vault",
        "workspace",
    }
)
CONST_SYSTEM_TEMP_DIRS: tuple[Path, ...] = (Path("/tmp"), Path("/var/tmp"))  # nosec B108
CONST_FORBIDDEN_SYSTEM_DIRS: tuple[Path, ...] = (
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/var"),
    Path("/sys"),
    Path("/proc"),
)

# ── Data Directories & Artifact Paths ─────────────────────────────────────────
CONST_ANALYSIS_DIR_NAME = "analysis"
CONST_REVIEWS_DIR_NAME = "reviews"
CONST_LOGS_DIR_NAME = "logs"
CONST_MODELS_DIR_NAME = "models"
CONST_CACHE_DIR_NAME = "cache"
CONST_CI_CACHE_FILENAME = "ci_cache.json"
CONST_LLM_CACHE_DIR_NAME = "llm"
CONST_BENCHMARKS_DIR_NAME = "benchmarks"
CONST_AUDIT_LOG_NAME = "audit.jsonl"
CONST_FEEDBACK_DATASET_NAME = "feedback_dataset.jsonl"
CONST_EMBEDDING_REPORT_FILENAME = "embedding_report.json"
CONST_TLS_DIR_NAME = "tls"
CONST_RAG_DIR_NAME = "rag"
CONST_INDEX_CACHE_FILENAME = "index_cache.json"
CONST_HALLUCINATIONS_FILE_NAME = "common_hallucinations.json"

# ── Memory & Byte Sizing Constants ────────────────────────────────────────────
CONST_FP32_BYTES_PER_ELEMENT: int = 4
CONST_KILOBYTE_BYTES: int = 1024

# ── TLS & Cryptographic Certificates ──────────────────────────────────────────
CONST_CA_CERT_NAME = "ca.crt"
CONST_CA_KEY_NAME = "ca.key"
CONST_SERVER_CERT_NAME = "tls.crt"
CONST_SERVER_KEY_NAME = "tls.key"
CONST_FULLCHAIN_CERT_NAME = "fullchain.crt"

# ── DevContainer ──────────────────────────────────────────────────────────────
CONST_DEVCONTAINER_DIR_NAME = ".devcontainer"
CONST_DEVCONTAINER_JSON_NAME = "devcontainer.json"
CONST_DEVCONTAINER_POST_CREATE_NAME = "postCreate.sh"
CONST_DEVCONTAINER_JSON_PATH = Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_JSON_NAME
CONST_DEVCONTAINER_POST_CREATE_PATH = (
    Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_POST_CREATE_NAME
)
CONST_DEVCONTAINER_IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/python:"
CONST_DEVCONTAINER_PUBLISHED_IMAGE = "ghcr.io/dan-petty/devops-cli/devcontainer:latest"
CONST_DEVCONTAINER_CLAUDE_EXTENSION: Final[str] = "anthropic.claude-code"
CONST_DEVCONTAINER_CLAUDE_FEATURE: Final[str] = (
    "ghcr.io/anthropics/devcontainer-features/claude-code:1"
)

# ── Specifications, Load Testing & Chaos ──────────────────────────────────────
CONST_SPECS_DIR_NAME = ".devops/specs"
CONST_SPECS_DIR_PATH = Path(CONST_SPECS_DIR_NAME)
CONST_CHAOS_DIR_NAME = "k8s/chaos"
CONST_CHAOS_DIR_PATH = Path(CONST_CHAOS_DIR_NAME)
CONST_LOAD_TESTS_DIR_NAME = "tests/load"
CONST_LOAD_TESTS_DIR_PATH = Path(CONST_LOAD_TESTS_DIR_NAME)

# ── OpenTofu & Infrastructure ──────────────────────────────────────────────────
CONST_TF_DIR_NAME = "tf"
CONST_TF_DIR_PATH = Path(CONST_TF_DIR_NAME)
CONST_TF_AWS_DIR = CONST_TF_DIR_PATH / "aws"
CONST_TF_AZURE_DIR = CONST_TF_DIR_PATH / "azure"
CONST_TF_GCP_DIR = CONST_TF_DIR_PATH / "gcp"
CONST_TF_ENVIRONMENTS_DIR = CONST_TF_DIR_PATH / "environments"
CONST_OPENTOFU_BINARIES: tuple[str, ...] = ("tofu", "terraform")


# ── Git & Workspace ───────────────────────────────────────────────────────────
CONST_GIT_DIR_NAME = ".git"
CONST_BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".db",
        ".sqlite",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".7z",
        ".rar",
        ".log",
    }
)
CONST_ENTITY_SEPARATOR = "/"

# ── Network & Remote Services ─────────────────────────────────────────────────
CONST_GITHUB_HOST = "github.com"
CONST_URL_SCHEME_HTTP = "http://"
CONST_URL_SCHEME_HTTPS = "https://"
CONST_GITHUB_SSH_PREFIX = "git@github.com:"
CONST_GITHUB_SSH_URL_PREFIX = "ssh://git@github.com/"
CONST_GITHUB_HTTP_PREFIX = "http://github.com/"
CONST_GITHUB_HTTPS_PREFIX = "https://github.com/"
CONST_GITHUB_REPO_SUFFIX = ".git"
CONST_GITHUB_RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "rate limit exceeded",
    "rate limit already exceeded",
    "secondary rate limit",
    "abuse-rate-limit",
    "too many requests",
    "http 429",
    "wait a few minutes before you try again",
)

CONST_URL_OLLAMA_LOCALHOST = "http://localhost:11434"
CONST_URL_ANTHROPIC_API_BASE = "https://api.anthropic.com"
CONST_URL_GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"
CONST_URL_OPENAI_API_BASE = "https://api.openai.com"
CONST_URL_GITHUB_API_BASE = "https://api.github.com"
CONST_URL_GITHUB_GRAPHQL = "https://api.github.com/graphql"
CONST_URL_K8S_DOWNLOAD_BASE = "https://dl.k8s.io"
CONST_URL_HELM_DOWNLOAD_BASE = "https://get.helm.sh"
CONST_URL_GITHUB_KUSTOMIZE_RELEASES_BASE = (
    "https://github.com/kubernetes-sigs/kustomize/releases/download"
)
CONST_URL_GITHUB_ARGO_WORKFLOWS_RELEASES_BASE = (
    "https://github.com/argoproj/argo-workflows/releases/download"
)
CONST_URL_GITHUB_ARGOCD_RELEASES_BASE = "https://github.com/argoproj/argo-cd/releases/download"
CONST_URL_GITHUB_ARGO_ROLLOUTS_RELEASES_BASE = (
    "https://github.com/argoproj/argo-rollouts/releases/download"
)

# ── Kubernetes & RFC 1123 Patterns ────────────────────────────────────────────
CONST_K8S_LABEL_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
CONST_K8S_SUBDOMAIN_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9.\-]{0,251}[a-z0-9])?$")
CONST_K8S_NODE_ROLE_LABEL_PREFIX = "node-role.kubernetes.io/"

# ── AI Prompt & Injection Mitigation ──────────────────────────────────────────
CONST_PROMPT_INJECTION_TAGS_RE: re.Pattern[str] = re.compile(
    r"<\/?(?:system|instructions?|prompt|untrusted)[^>]*>",
    re.IGNORECASE,
)
CONST_PROMPT_INJECTION_TAGS_REGEX = CONST_PROMPT_INJECTION_TAGS_RE

# ── File Permissions ──────────────────────────────────────────────────────────
CONST_PERM_DIR = 0o700
CONST_PERM_PRIVATE_KEY = 0o600
CONST_PERM_PUBLIC_KEY = 0o644
CONST_PERM_EXEC = 0o755

CONST_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
CONST_MAX_PROBE_FILE_SIZE_BYTES: Final[int] = (
    512 * 1024
)  # 512 KiB pre-flight file size cap for review probes
CONST_PROBE_MANIFEST_NAMES: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "package.json",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
)

# ── Code Review & Analysis ────────────────────────────────────────────────────
CONST_REVIEW_GENERATED_FILES = frozenset(
    {
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
        "Cargo.lock",
    }
)
CONST_SSH_GRACE_DAYS = 7

CONST_STATUS_VERIFIED = "VERIFIED"
CONST_STATUS_UNVERIFIED = "UNVERIFIED"
CONST_STATUS_INVALIDATED = "INVALIDATED"
CONST_STATUS_MITIGATED = "MITIGATED"
CONST_STATUS_SUCCESS = "SUCCESS"

CONST_GIT_MAIN_BRANCH = "main"
CONST_DEFAULT_LINE_NUMBER = 1
CONST_MARKDOWN_HEADING_LEVEL = 3

CONST_STANDARD_HTML_TAGS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "details",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)

CONST_RECOMMENDATION_APPROVE = "APPROVE"
CONST_RECOMMENDATION_REQUEST_CHANGES = "REQUEST CHANGES"
CONST_RECOMMENDATION_BLOCK = "BLOCK"

# ── GitHub CLI & Pull Requests ────────────────────────────────────────────────
CONST_GH_CLI = "gh"
CONST_GH_QUOTA_CACHE_FILENAME = "gh_quota.json"
CONST_GH_ETAG_CACHE_FILENAME = "gh_etag_cache.json"
CONST_GH_HEADER_ETAG = "ETag"
CONST_GH_HEADER_IF_NONE_MATCH = "If-None-Match"
CONST_GH_HEADER_USER_AGENT = "devops-cli"
CONST_GH_WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"
CONST_GH_NON_API_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "auth",
        "version",
        "--version",
        "help",
        "--help",
    }
)
CONST_GH_FAILING_CHECK_CONCLUSIONS: Final[frozenset[str]] = frozenset(
    {
        "failure",
        "timed_out",
        "cancelled",
        "action_required",
        "startup_failure",
    }
)
CONST_PR_API_STATE_MAP: Final[dict[str, str]] = {
    "all": "all",
    "closed": "closed",
    "merged": "closed",
}
CONST_BRANCH_PREFIXES: tuple[str, ...] = (
    "feat/",
    "fix/",
    "docs/",
    "chore/",
    "refactor/",
    "release/",
)

# ── Exception & Domain Error Codes ────────────────────────────────────────────
CONST_ERROR_CODE_DEVOPS_CLI = "DEVOPS_CLI_ERROR"
CONST_ERROR_CODE_LLM_INFERENCE = "LLM_INFERENCE_ERROR"
CONST_ERROR_CODE_CONFIG = "CONFIGURATION_ERROR"
CONST_ERROR_CODE_GIT = "GIT_OPERATION_ERROR"
CONST_ERROR_CODE_SECURITY = "SECURITY_ERROR"
CONST_ERROR_CODE_TOOL = "TOOL_EXECUTION_ERROR"
CONST_ERROR_CODE_VALIDATION = "VALIDATION_ERROR"
CONST_ERROR_CODE_VAULT = "VAULT_ERROR"
CONST_ERROR_CODE_VAULT_AUTH = "VAULT_AUTH_ERROR"
CONST_ERROR_CODE_VAULT_LEASE = "VAULT_LEASE_ERROR"
CONST_ERROR_CODE_VALKEY = "VALKEY_ERROR"
CONST_ERROR_CODE_DOCKER_SANDBOX = "DOCKER_SANDBOX_ERROR"
CONST_ERROR_CODE_DOCKER_ENGINE = "DOCKER_ENGINE_ERROR"
CONST_ERROR_CODE_DOCKER_DAEMON_UNAVAILABLE = "DOCKER_DAEMON_UNAVAILABLE"
CONST_ERROR_CODE_K8S = "K8S_ERROR"
CONST_ERROR_CODE_ARGO = "ARGO_ERROR"
CONST_ERROR_CODE_ARGO_RESOURCE_NOT_FOUND = "ARGO_RESOURCE_NOT_FOUND"
CONST_ERROR_CODE_MODEL_BUNDLE = "MODEL_BUNDLE_ERROR"
CONST_ERROR_CODE_HARNESS = "HARNESS_ERROR"
CONST_ERROR_CODE_HARNESS_VALIDATION = "HARNESS_VALIDATION_ERROR"
CONST_ERROR_CODE_HARNESS_EXECUTION = "HARNESS_EXECUTION_ERROR"
CONST_ERROR_CODE_CONSTELLATION_QUIESCE = "CONSTELLATION_QUIESCE_ERROR"
CONST_ERROR_CODE_CONSTELLATION_FAILOVER = "CONSTELLATION_FAILOVER_ERROR"
CONST_ERROR_CODE_CONSTELLATION_RESUME = "CONSTELLATION_RESUME_ERROR"
CONST_ERROR_CODE_REVIEW_POOL = "REVIEW_POOL_ERROR"
CONST_ERROR_CODE_TELEMETRY = "TELEMETRY_ERROR"
CONST_ERROR_CODE_LOGFIRE = "LOGFIRE_CONFIG_ERROR"
CONST_ERROR_CODE_LIBRARY_INGESTION = "LIBRARY_INGESTION_ERROR"
CONST_ERROR_CODE_LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND_ERROR"
CONST_ERROR_CODE_DOCS_INGESTION = "DOCS_INGESTION_ERROR"
CONST_ERROR_CODE_DOC_COMPACTION = "DOC_COMPACTION_ERROR"
CONST_ERROR_CODE_SANDBOX = "SANDBOX_ERROR"
CONST_ERROR_CODE_SANDBOX_VALIDATION = "SANDBOX_VALIDATION_ERROR"
CONST_ERROR_CODE_SANDBOX_PORT_ALLOCATION = "SANDBOX_PORT_ALLOCATION_ERROR"
CONST_ERROR_CODE_SANDBOX_NOT_FOUND = "SANDBOX_NOT_FOUND_ERROR"
CONST_ERROR_CODE_COSIGN = "COSIGN_ERROR"
CONST_ERROR_CODE_COSIGN_VERIFY = "COSIGN_VERIFICATION_FAILED"
CONST_ERROR_CODE_STRUCTURED_VALIDATION = "STRUCTURED_VALIDATION_ERROR"
CONST_MAX_ERROR_DETAIL_LENGTH = 256

# ── AI Client Structured Output Metric Invariants ─────────────────────────────
CONST_METRIC_AI_STRUCTURED_SUCCESS = "ai.client.structured_success"
CONST_METRIC_AI_STRUCTURED_REPAIR_SUCCESS = "ai.client.structured_repair_success"
CONST_METRIC_AI_STRUCTURED_RETRY_COUNT = "ai.client.structured_retry_count"
CONST_METRIC_AI_STRUCTURED_VALIDATION_FAILURE = "ai.client.structured_validation_failure"


CONST_EXIT_SUCCESS: int = 0
CONST_EXIT_FAILURE: int = 1
CONST_EXIT_ERROR_INFERENCE: int = 10

CONST_MSG_KEYRING_UNAVAILABLE = "OS Keyring service is unavailable; run in headless CI mode"
CONST_MSG_BRANCH_INVALID = "Branch name is invalid"
CONST_MSG_URL_INVALID = "Invalid URL format or scheme"
CONST_MSG_SSRF_RESOLVES_PRIVATE = "Target resolves to a private or loopback network endpoint"

# ── Telemetry Invariants ──────────────────────────────────────────────────────
CONST_OTEL_SCOPE_NAME = "devops-cli.telemetry"
CONST_OTEL_SPAN_KIND_INTERNAL = "internal"
CONST_OTEL_METRIC_UNIT_ONE = "1"
CONST_OTEL_SERVICE_NAME = "devops-cli"

# ── Network Reference & Egress Security Invariants ────────────────────────────
# RFC 2606 Reserved Top-Level Domains for testing & documentation
CONST_RFC2606_RESERVED_TLDS: frozenset[str] = frozenset(
    {
        "test",
        "example",
        "invalid",
    }
)

# RFC 2606 and RFC 6761 Reserved Second-Level Domains
CONST_RFC2606_RESERVED_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "example.edu",
    }
)

# Special-use and private infrastructure TLDs / suffixes (RFC 6762, RFC 8375, Kubernetes)
CONST_SPECIAL_USE_TLDS: frozenset[str] = frozenset(
    {
        "local",
        "internal",
        "lan",
        "corp",
        "home.arpa",
        "onion",
        "arpa",
        "cluster.local",
        "localdomain",
        "svc",
    }
)

# Authoritative public registries and documentation schemas excluded from external egress audits
CONST_EXCLUDED_PUBLIC_REGISTRIES: frozenset[str] = frozenset(
    {
        "schema.org",
        "w3.org",
        "json-schema.org",
        "opencontainers.org",
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "pypi.org",
        "pypi.python.org",
        "pythonhosted.org",
        "files.pythonhosted.org",
        "npmjs.com",
        "npmjs.org",
        "registry.npmjs.org",
        "yarnpkg.com",
        "registry.yarnpkg.com",
        "crates.io",
        "static.crates.io",
        "golang.org",
        "pkg.go.dev",
        "proxy.golang.org",
        "sum.golang.org",
        "rubygems.org",
        "maven.org",
        "apache.org",
        "gradle.org",
        "packagist.org",
        "nuget.org",
        "google.com",
        "osv.dev",
        "nist.gov",
        "shodan.io",
        "cloudflare.com",
    }
)


# Standard object-oriented receivers in Python
CONST_STANDARD_RECEIVER_IDENTIFIERS: frozenset[str] = frozenset({"self", "cls"})

# Common code receiver, module, or telemetry metric prefixes
CONST_CODE_CONFIG_PREFIXES: tuple[str, ...] = (
    "self.",
    "cls.",
    "cli.",
    "agent.",
    "process.",
    "ci.step.",
    "ci.",
    "telemetry.",
    "logger.",
    "log.",
    "mcp.",
    "metric.",
    "otel.",
)

# Common property and telemetry metric leaf attributes
CONST_COMMON_PROPERTY_SUFFIXES: frozenset[str] = frozenset(
    {
        "name",
        "email",
        "actor",
        "pid",
        "group",
        "security",
        "docs",
        "ping",
        "call",
        "run",
        "post",
        "collection",
        "sdk",
        "executable",
        "runtime",
        "total",
        "tools",
        "count",
        "size",
        "duration",
        "seconds",
        "ms",
        "bytes",
        "status",
        "state",
        "type",
        "id",
        "rate",
        "ratio",
        "max",
        "min",
        "avg",
        "sum",
        "mean",
        "input",
        "output",
        "calls",
        "errors",
        "exceptions",
        "failures",
        "successes",
        "latency",
        "value",
        "result",
        "payload",
        "level",
        "severity",
        "limit",
        "threshold",
    }
)

# MIME types that correspond to top-level domains or legacy formats and should not classify domains as files
CONST_EXCLUDED_FILE_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/x-msdos-program",
        "application/vnd.lotus-organizer",
        "text/org",
    }
)

# Common telemetry, metric, and logging invocation function names
CONST_TELEMETRY_CALL_NAMES: frozenset[str] = frozenset(
    {
        "record_metric",
        "metric_counter",
        "set_attribute",
        "add_attribute",
        "counter",
        "gauge",
        "histogram",
        "meter",
        "logfire",
        "otel",
        "telemetry",
        "statsd",
        "prometheus",
    }
)

# ── Review Finding Consolidation Signals ─────────────────────────────────────
# Identifiers too generic to prove two findings describe the same defect. Kept here
# (never inline) so the list stays auditable for over-matching, per the brittle-subset
# prohibition: it only ever *weakens* a duplicate signal, never invalidates a finding.
REVIEW_GENERIC_SYMBOL_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "the",
        "and",
        "not",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "when",
        "self",
        "none",
        "true",
        "false",
        "str",
        "int",
        "dict",
        "list",
        "set",
        "any",
        "type",
        "class",
        "def",
        "return",
        "value",
        "values",
        "name",
        "names",
        "data",
        "path",
        "paths",
        "file",
        "files",
        "line",
        "lines",
        "code",
        "test",
        "tests",
        "error",
        "errors",
        "exception",
        "result",
        "results",
        "config",
        "settings",
        "method",
        "function",
        "module",
        "object",
        "param",
        "params",
        "arg",
        "args",
        "kwargs",
        "input",
        "output",
        "call",
        "calls",
        "user",
        "users",
        "http",
        "https",
        "api",
        "url",
        "urls",
        "time",
        "size",
        "count",
        "index",
        "key",
        "keys",
        "item",
        "items",
        "state",
        "status",
        "message",
        "messages",
        "log",
        "logs",
        "logger",
    }
)

# Minimum length at which a single shared identifier is specific enough, on its own,
# to conclude two findings describe the same defect.
REVIEW_STRONG_SYMBOL_MIN_LENGTH: Final[int] = 6

# Minimum description token overlap required before two findings that merely share an
# enclosing symbol are treated as one defect. Set high enough that different defects in
# the same function stay separate, since dropping a real finding is the costlier error.
REVIEW_DESCRIPTION_SIMILARITY_THRESHOLD: Final[float] = 0.35
# ── Unified Secret Resolution & Vault Lease Lifecycle ────────────────────────
# Provider identifiers recorded in the credential access audit trail.
CONST_SECRET_PROVIDER_KEYRING: Final[str] = "keyring"
CONST_SECRET_PROVIDER_VAULT: Final[str] = "vault"
CONST_SECRET_PROVIDER_ENVIRONMENT: Final[str] = "environment"
CONST_SECRET_PROVIDER_SETTINGS: Final[str] = "settings"
CONST_SECRET_PROVIDER_TOOL: Final[str] = "tool"

# Upper bound on retained credential access records, preventing unbounded growth in
# long-running sessions. The trail records provider and outcome only, never values.
CONST_SECRET_AUDIT_MAX_ENTRIES: Final[int] = 1000

# Vault API paths. Fixed by the Vault HTTP API, so this set is closed and exhaustive.
CONST_VAULT_API_PREFIX: Final[str] = "/v1"
# Conventional KV-v2 mount and folder holding this project's managed credentials.
CONST_VAULT_SECRET_MOUNT: Final[str] = "secret/data/devops-cli"
CONST_VAULT_PATH_APPROLE_LOGIN: Final[str] = "auth/approle/login"
CONST_VAULT_PATH_KUBERNETES_LOGIN: Final[str] = "auth/kubernetes/login"

# Supported Vault authentication methods, closed by what this CLI implements.
CONST_VAULT_AUTH_METHODS: Final[frozenset[str]] = frozenset({"approle", "kubernetes"})
CONST_VAULT_PATH_TOKEN_LOOKUP_SELF: Final[str] = "auth/token/lookup-self"
CONST_VAULT_PATH_TOKEN_RENEW_SELF: Final[str] = "auth/token/renew-self"
CONST_VAULT_PATH_LEASE_RENEW: Final[str] = "sys/leases/renew"
CONST_VAULT_PATH_LEASE_REVOKE: Final[str] = "sys/leases/revoke"
CONST_VAULT_PATH_TRANSIT_ENCRYPT: Final[str] = "transit/encrypt"
CONST_VAULT_PATH_TRANSIT_DECRYPT: Final[str] = "transit/decrypt"

# Default in-cluster ServiceAccount token projected into every Kubernetes pod.
CONST_KUBERNETES_SA_TOKEN_PATH: Final[str] = "/var/run/secrets/kubernetes.io/serviceaccount/token"

# ── Grafana Dashboard Schema ─────────────────────────────────────────────────
# Grafana lays dashboards out on a fixed 24-column grid; a panel extending past it is
# clipped rather than wrapped.
CONST_GRAFANA_DASHBOARD_GRID_WIDTH: Final[int] = 24
# Dashboard JSON schema version targeted by the generated models (Grafana 10+).
CONST_GRAFANA_SCHEMA_VERSION: Final[int] = 39
CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE: Final[str] = "prometheus"

# Panel types emitted by the builder library.
CONST_GRAFANA_PANEL_TYPE_TIMESERIES: Final[str] = "timeseries"
CONST_GRAFANA_PANEL_TYPE_STAT: Final[str] = "stat"
CONST_GRAFANA_PANEL_TYPE_ROW: Final[str] = "row"

# ── PromQL Structural Validation ─────────────────────────────────────────────
# Bracket pairs used by the PromQL grammar. Closed and exhaustive: these are the only
# grouping delimiters the language defines.
CONST_PROMQL_BRACKET_PAIRS: Final[dict[str, str]] = {"(": ")", "[": "]", "{": "}"}

# Quote characters that open a PromQL string literal.
CONST_PROMQL_QUOTE_CHARS: Final[frozenset[str]] = frozenset({'"', "'", "`"})

# Duration units defined by the PromQL time-duration grammar. Closed and exhaustive per
# the Prometheus query language specification.
CONST_PROMQL_DURATION_UNITS: Final[frozenset[str]] = frozenset({"ms", "s", "m", "h", "d", "w", "y"})

# ── Tiered Cache Namespacing & Tiers ─────────────────────────────────────────
# Root prefix for every cache key this project writes, so a shared Valkey instance can
# be swept per-project and keys never collide with another tenant's.
CONST_CACHE_NAMESPACE_ROOT: Final[str] = "devops-cli"
CONST_CACHE_KEY_SEPARATOR: Final[str] = ":"

# Cache tiers. Closed set: L1 is the in-process LRU, L2 is Valkey, and L1_L2 writes both.
CONST_CACHE_TIER_L1: Final[str] = "l1"
CONST_CACHE_TIER_L2: Final[str] = "l2"
CONST_CACHE_TIER_L1_L2: Final[str] = "l1_l2"
CONST_CACHE_TIERS: Final[frozenset[str]] = frozenset(
    {CONST_CACHE_TIER_L1, CONST_CACHE_TIER_L2, CONST_CACHE_TIER_L1_L2}
)

# ── Source & Test Tree Layout ────────────────────────────────────────────────
# Repository layout conventions used to map changed sources onto covering tests.
CONST_SOURCE_ROOT_DIR: Final[str] = "src"
CONST_TESTS_ROOT_DIR: Final[str] = "tests"
CONST_TEST_FILE_PREFIX: Final[str] = "test_"
CONST_PYTHON_FILE_SUFFIX: Final[str] = ".py"

# ── Terraform / OpenTofu HCL AST Analysis ────────────────────────────────────
# HCL configuration file extensions recognised by Terraform and OpenTofu.
CONST_HCL_FILE_EXTENSIONS: Final[tuple[str, ...]] = (".tf",)
CONST_HCL_JSON_FILE_EXTENSION: Final[str] = ".tf.json"

# Candidate state file names, in the order Terraform and OpenTofu resolve them.
CONST_TF_STATE_FILE_NAMES: Final[tuple[str, ...]] = (
    "terraform.tfstate",
    ".terraform/terraform.tfstate",
)

# Top-level HCL block types. This set is closed and exhaustive: it is fixed by the
# Terraform and OpenTofu configuration language grammar, not inferred from samples.
CONST_HCL_BLOCK_RESOURCE: Final[str] = "resource"
CONST_HCL_BLOCK_DATA: Final[str] = "data"
CONST_HCL_BLOCK_MODULE: Final[str] = "module"
CONST_HCL_BLOCK_VARIABLE: Final[str] = "variable"
CONST_HCL_BLOCK_OUTPUT: Final[str] = "output"
CONST_HCL_BLOCK_LOCALS: Final[str] = "locals"
CONST_HCL_BLOCK_PROVIDER: Final[str] = "provider"
CONST_HCL_BLOCK_TERRAFORM: Final[str] = "terraform"
CONST_HCL_BLOCK_MOVED: Final[str] = "moved"
CONST_HCL_BLOCK_IMPORT: Final[str] = "import"
CONST_HCL_BLOCK_CHECK: Final[str] = "check"

CONST_HCL_BLOCK_TYPES: Final[frozenset[str]] = frozenset(
    {
        CONST_HCL_BLOCK_RESOURCE,
        CONST_HCL_BLOCK_DATA,
        CONST_HCL_BLOCK_MODULE,
        CONST_HCL_BLOCK_VARIABLE,
        CONST_HCL_BLOCK_OUTPUT,
        CONST_HCL_BLOCK_LOCALS,
        CONST_HCL_BLOCK_PROVIDER,
        CONST_HCL_BLOCK_TERRAFORM,
        CONST_HCL_BLOCK_MOVED,
        CONST_HCL_BLOCK_IMPORT,
        CONST_HCL_BLOCK_CHECK,
    }
)

# Marker key `python-hcl2` injects to distinguish blocks from plain attribute maps.
CONST_HCL_BLOCK_MARKER: Final[str] = "__is_block__"

# Traversal prefixes that do NOT address another resource, so they create no dependency
# edge. Closed and exhaustive: these are the named values defined by the configuration
# language's expression grammar, not an inferred subset.
CONST_HCL_NON_RESOURCE_NAMESPACES: Final[frozenset[str]] = frozenset(
    {"var", "local", "each", "count", "path", "self", "terraform"}
)

# ── Argo CRD Group, Version & Resource Plurals ───────────────────────────────
# The Argo project serves Applications, ApplicationSets, Rollouts, AnalysisRuns,
# and Workflows from a single API group. These identifiers are fixed by the
# published Argo CRD manifests, so the set is closed and exhaustive.
CONST_ARGO_API_GROUP: Final[str] = "argoproj.io"
CONST_ARGO_API_VERSION: Final[str] = "v1alpha1"

CONST_ARGO_PLURAL_APPLICATIONS: Final[str] = "applications"
CONST_ARGO_PLURAL_APPLICATION_SETS: Final[str] = "applicationsets"
CONST_ARGO_PLURAL_ROLLOUTS: Final[str] = "rollouts"
CONST_ARGO_PLURAL_ANALYSIS_RUNS: Final[str] = "analysisruns"
CONST_ARGO_PLURAL_WORKFLOWS: Final[str] = "workflows"

CONST_ARGO_RESOURCE_PLURALS: Final[frozenset[str]] = frozenset(
    {
        CONST_ARGO_PLURAL_APPLICATIONS,
        CONST_ARGO_PLURAL_APPLICATION_SETS,
        CONST_ARGO_PLURAL_ROLLOUTS,
        CONST_ARGO_PLURAL_ANALYSIS_RUNS,
        CONST_ARGO_PLURAL_WORKFLOWS,
    }
)

# Argo Rollouts control-plane fields. The rollouts controller watches these
# exact fields to drive promotion, abort, and restart, which is what the
# `kubectl argo rollouts` plugin patches on the user's behalf.
CONST_ROLLOUT_FIELD_ABORT: Final[str] = "abort"
CONST_ROLLOUT_FIELD_PROMOTE_FULL: Final[str] = "promoteFull"
CONST_ROLLOUT_FIELD_PAUSE_CONDITIONS: Final[str] = "pauseConditions"
CONST_ROLLOUT_FIELD_CONTROLLER_PAUSE: Final[str] = "controllerPause"
CONST_ROLLOUT_FIELD_RESTART_AT: Final[str] = "restartAt"

# Terminal Argo Workflow phases. Closed set defined by the Argo Workflows
# controller's `status.phase` enumeration.
CONST_ARGO_WORKFLOW_PHASE_SUCCEEDED: Final[str] = "Succeeded"
CONST_ARGO_WORKFLOW_PHASE_FAILED: Final[str] = "Failed"
CONST_ARGO_WORKFLOW_PHASE_ERROR: Final[str] = "Error"

CONST_ARGO_WORKFLOW_FAILURE_PHASES: Final[frozenset[str]] = frozenset(
    {CONST_ARGO_WORKFLOW_PHASE_FAILED, CONST_ARGO_WORKFLOW_PHASE_ERROR}
)
CONST_ARGO_WORKFLOW_TERMINAL_PHASES: Final[frozenset[str]] = (
    CONST_ARGO_WORKFLOW_FAILURE_PHASES | frozenset({CONST_ARGO_WORKFLOW_PHASE_SUCCEEDED})
)

# ── Docker Engine Socket API & BuildKit Cache Introspection ──────────────────
# Container CPU utilisation severity thresholds for live stats rendering.
CONST_DOCKER_CPU_WARNING_PERCENT: Final[float] = 50.0
CONST_DOCKER_CPU_CRITICAL_PERCENT: Final[float] = 80.0

# Default rootful and rootless Docker daemon Unix domain socket endpoints. The
# Engine API is spoken directly over these sockets, eliminating `docker` CLI churn.
CONST_DOCKER_UNIX_SOCKET_PATH: Final[str] = "/var/run/docker.sock"
CONST_DOCKER_UNIX_SOCKET_URL: Final[str] = "unix:///var/run/docker.sock"
CONST_DOCKER_HOST_ENV_VAR: Final[str] = "DOCKER_HOST"

# DOCKER_HOST schemes that address a network endpoint and therefore require SSRF
# validation before the Engine API client is constructed. Closed, exhaustive set
# defined by the Docker Engine daemon socket grammar (`dockerd -H`).
CONST_DOCKER_NETWORK_HOST_SCHEMES: Final[tuple[str, ...]] = ("tcp://", "http://", "https://")

# `GET /system/df` object types returned by the Engine API disk-usage endpoint.
CONST_DOCKER_DF_BUILD_CACHE_KEY: Final[str] = "BuildCache"
CONST_DOCKER_DF_IMAGES_KEY: Final[str] = "Images"
CONST_DOCKER_DF_CONTAINERS_KEY: Final[str] = "Containers"
CONST_DOCKER_DF_VOLUMES_KEY: Final[str] = "Volumes"

# BuildKit build-cache record types emitted by `GET /system/df` (buildkit solver
# vertex classes). Exhaustive per the BuildKit cache record schema.
CONST_DOCKER_BUILD_CACHE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "internal",
        "frontend",
        "source.local",
        "source.git.checkout",
        "exec.cachemount",
        "regular",
    }
)

# Sensitive host configuration and credential directories forbidden from container sandbox mounts
CONST_SANDBOX_SENSITIVE_SUBPATHS: Final[frozenset[str]] = frozenset(
    {
        ".ssh",
        ".aws",
        ".kube",
        ".git",
    }
)

# Multi-tier sandbox networking mode constants
CONST_SANDBOX_NETWORK_ISOLATED: Final[str] = "isolated"
CONST_SANDBOX_NETWORK_NAMESPACE: Final[str] = "sandbox_namespace"
CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST: Final[str] = "public_whitelist"
CONST_SANDBOX_NETWORK_LOCAL_WHITELIST: Final[str] = "local_whitelist"
CONST_SANDBOX_NETWORK_BRIDGE: Final[str] = "bridge"

CONST_SANDBOX_DEFAULT_NAMESPACE: Final[str] = "sandbox"
CONST_SANDBOX_DOCKER_INTERNAL_NET: Final[str] = "devops-sandbox-net"

# Exit status reported when a sandbox workload exceeds its wall-clock budget,
# matching the conventional GNU coreutils `timeout` termination code.
CONST_SANDBOX_TIMEOUT_EXIT_CODE: Final[int] = 124

CONST_SANDBOX_NETWORK_MODES: Final[frozenset[str]] = frozenset(
    {
        CONST_SANDBOX_NETWORK_ISOLATED,
        CONST_SANDBOX_NETWORK_NAMESPACE,
        CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
        CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
        CONST_SANDBOX_NETWORK_BRIDGE,
    }
)

CONST_SANDBOX_NETWORK_MODE_ALIASES: Final[dict[str, str]] = {
    "isolated": CONST_SANDBOX_NETWORK_ISOLATED,
    "none": CONST_SANDBOX_NETWORK_ISOLATED,
    "isolated_pod": CONST_SANDBOX_NETWORK_ISOLATED,
    "isolated-pod": CONST_SANDBOX_NETWORK_ISOLATED,
    "sandbox_namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "sandbox-namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "internal": CONST_SANDBOX_NETWORK_NAMESPACE,
    "public_whitelist": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "public-whitelist": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "public": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "local_whitelist": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "local-whitelist": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "local": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "bridge": CONST_SANDBOX_NETWORK_BRIDGE,
}

# Falco runtime security severity hierarchy
CONST_FALCO_SEVERITY_LEVELS: Final[dict[str, int]] = {
    "DEBUG": 0,
    "INFO": 1,
    "INFORMATIONAL": 1,
    "NOTICE": 2,
    "WARNING": 3,
    "ERROR": 4,
    "CRITICAL": 5,
    "ALERT": 6,
    "EMERGENCY": 7,
}

CONST_MIN_SECURITY_STREAM_DURATION: Final[int] = 1
CONST_MAX_SECURITY_STREAM_DURATION: Final[int] = 3600
CONST_MIN_SECURITY_STREAM_TAIL_LINES: Final[int] = 1
CONST_MAX_SECURITY_STREAM_TAIL_LINES: Final[int] = 10000

# Threat intelligence distributed caching
CONST_THREAT_INTEL_CACHE_PREFIX: Final[str] = "valkey:threat_intel:domain"

# RAG embedding distributed caching
CONST_VALKEY_EMBEDDING_PREFIX: Final[str] = "valkey:rag:embedding"

# GitHub CLI rate limiter mutation verbs and HTTP methods
CONST_GH_MUTATION_VERBS: Final[frozenset[str]] = frozenset(
    {
        "edit",
        "create",
        "delete",
        "add",
        "close",
        "reopen",
        "merge",
        "comment",
        "item-edit",
        "item-add",
        "item-delete",
        "field-create",
        "field-delete",
        "ready",
        "resolve",
        "archive",
        "sync",
        "set",
    }
)

CONST_GH_MUTATION_HTTP_METHODS: Final[frozenset[str]] = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
)

# ── AI Gateway & Distributed Router Constants ─────────────────────────────────
CONST_AI_GATEWAY_VIRTUAL_MODELS: Final[tuple[str, ...]] = (
    "devops-chat",
    "devops-coder",
    "devops-reasoning",
    "devops-embedding",
)
CONST_AI_GATEWAY_PROVIDER: Final[str] = "gateway"
CONST_AI_GATEWAY_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey")
CONST_AI_GATEWAY_PROVIDER_LITELLM: Final[str] = "litellm"
CONST_AI_GATEWAY_PROVIDER_PORTKEY: Final[str] = "portkey"
CONST_AI_GATEWAY_DEFAULT_PORT: Final[int] = 4000
CONST_AI_PORTKEY_DEFAULT_PORT: Final[int] = 8787
CONST_AI_LIGHTLLM_DEFAULT_PORT: Final[int] = 8000
CONST_AI_BACKEND_LIGHTLLM: Final[str] = "lightllm"
CONST_AI_BACKENDS: Final[tuple[str, ...]] = ("ollama", "vllm", "lightllm")
CONST_AI_PROMPT_CACHE_TTL_5M: Final[str] = "5m"
CONST_AI_PROMPT_CACHE_TTL_1H: Final[str] = "1h"
CONST_AI_PROMPT_CACHE_TTLS: Final[tuple[str, ...]] = ("5m", "1h")
CONST_AI_CASCADE_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey", "lightllm", "ollama")
CONST_AI_DEFAULT_CACHE_MARKER_KIND: Final[str] = "cache-point"
CONST_AI_ALLOW_PRIVATE_NETWORK_ENV: Final[str] = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"
CONST_TASK_TAXONOMY_EMBEDDING: Final[frozenset[str]] = frozenset(
    {"embedding", "embed_documents", "vector_index", "rag_index", "semantic_search"}
)
CONST_TASK_TAXONOMY_CODER: Final[frozenset[str]] = frozenset(
    {
        "persona_review",
        "verify_finding",
        "test_gen",
        "ast_analysis",
        "codegen",
        "review",
        "refactor",
    }
)
CONST_TASK_TAXONOMY_REASONING: Final[frozenset[str]] = frozenset(
    {
        "architecture",
        "threat_model",
        "cross_repo",
        "novel_synthesis",
        "adversarial_debate",
        "deep_review",
        "synthesis",
    }
)

# ── Strategic Roadmap Taxonomy & Synchronization Constants ────────────────────
CONST_ROADMAP_SCOPE_KEYWORDS: Final[dict[str, frozenset[str]]] = {
    "scope/github": frozenset(
        {"pm", "github", "project", "backlog", "sprint", "kanban", "pr", "prs", "fleet", "daemon"}
    ),
    "scope/ai": frozenset(
        {
            "ai",
            "mcts",
            "explore",
            "syntopical",
            "forage",
            "socratic",
            "reasoning",
            "model",
            "prompt",
            "llm",
            "embedding",
            "rag",
        }
    ),
    "scope/k8s": frozenset(
        {
            "k8s",
            "kubernetes",
            "pod",
            "pods",
            "cluster",
            "minikube",
            "helm",
            "argo",
            "argocd",
            "rollout",
        }
    ),
    "scope/security": frozenset(
        {"sec", "vault", "security", "fuzz", "cve", "trivy", "gitleaks", "semgrep"}
    ),
    "scope/review": frozenset({"review", "finding", "findings", "hallucination"}),
    "scope/docs": frozenset({"docs", "roadmap", "compaction"}),
    "scope/telemetry": frozenset(
        {"telemetry", "metric", "metrics", "tracing", "trace", "loki", "jaeger", "prometheus"}
    ),
    "scope/mcp": frozenset({"mcp", "fastmcp"}),
    "scope/config": frozenset({"config", "settings", "keyring"}),
}

CONST_ROADMAP_PRIORITY_TAGS: Final[dict[str, tuple[str, ...]]] = {
    "priority/p0-critical": ("p0", "blocker", "critical"),
    "priority/p1-high": ("p1", "high"),
    "priority/p2-medium": ("p2", "medium"),
    "priority/p3-low": ("p3", "low"),
}

# ── Multi-Scale Semantic Outline & Inspection Scanner ────────────────────────
CONST_MAX_INSPECT_FILE_SIZE_BYTES: Final[int] = 50 * 1024 * 1024  # 50 MiB limit
CONST_DEFAULT_FOCAL_WINDOW_SIZE: Final[int] = 30
CONST_HOTSPOT_COMPLEXITY_THRESHOLD: Final[int] = 5

# ── File Classification & Review Context Taxonomy ─────────────────────────────
CONST_DOC_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".asciidoc",
        ".tex",
    }
)

CONST_DOC_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "license",
        "copying",
        "notice",
        "authors",
        "contributors",
        "changelog",
        "readme",
        "agents.md",
        "claude.md",
    }
)

CONST_CONFIG_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".tf",
        ".hcl",
        ".xml",
        ".properties",
        ".plist",
    }
)

CONST_CONFIG_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "dockerfile",
        "containerfile",
        ".dockerignore",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".flake8",
        ".pylintrc",
        "helmfile.yaml",
        "chart.yaml",
        "values.yaml",
        "kustomization.yaml",
    }
)

CONST_CODE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".kts",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".lua",
    }
)

CONST_AI_SPEND_TABLE_NAME: Final[str] = "ai_spend_records"

CONST_RESEARCH_DIR_NAME: Final[str] = "research"
CONST_DEFAULT_MAX_SYNTOPICAL_SOURCES: Final[int] = 20
CONST_SYNTOPICAL_MIN_RELEVANCE: Final[float] = 0.2
CONST_SYNTOPICAL_MAX_EXCERPT_CHARS: Final[int] = 1000

# ── Kubernetes Informer & Service Constants ──────────────────────────────────
CONST_K8S_EVENT_ADDED: Final[str] = "ADDED"
CONST_K8S_EVENT_MODIFIED: Final[str] = "MODIFIED"
CONST_K8S_EVENT_DELETED: Final[str] = "DELETED"
CONST_K8S_EVENT_ERROR: Final[str] = "ERROR"
CONST_K8S_INFORMER_EVENTS: Final[tuple[str, ...]] = (
    CONST_K8S_EVENT_ADDED,
    CONST_K8S_EVENT_MODIFIED,
    CONST_K8S_EVENT_DELETED,
    CONST_K8S_EVENT_ERROR,
)

# ── Dashboard TUI Domains ────────────────────────────────────────────────────
# Each domain is one tab of the workstation dashboard, refreshed by its own worker.
CONST_DASHBOARD_DOMAIN_K8S: Final[str] = "k8s"
CONST_DASHBOARD_DOMAIN_DOCKER: Final[str] = "docker"
CONST_DASHBOARD_DOMAIN_TELEMETRY: Final[str] = "telemetry"
CONST_DASHBOARD_DOMAIN_AI: Final[str] = "ai"
CONST_DASHBOARD_DOMAIN_VALKEY: Final[str] = "valkey"
CONST_DASHBOARD_DOMAINS: Final[tuple[str, ...]] = (
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_VALKEY,
)
# Human-readable labels used for tab titles and status banners.
CONST_DASHBOARD_DOMAIN_LABELS: Final[dict[str, str]] = {
    CONST_DASHBOARD_DOMAIN_K8S: "Kubernetes",
    CONST_DASHBOARD_DOMAIN_DOCKER: "Docker",
    CONST_DASHBOARD_DOMAIN_TELEMETRY: "Telemetry",
    CONST_DASHBOARD_DOMAIN_AI: "AI Review",
    CONST_DASHBOARD_DOMAIN_VALKEY: "Valkey Cache",
}

# ── Docker Resource Sub-Tabs ─────────────────────────────────────────────────
# Every Docker resource lives under the single Docker tab and is projected from one
# DockerSummary, so the whole inventory costs one daemon round trip per refresh.
CONST_DOCKER_RESOURCE_CONTAINERS: Final[str] = "containers"
CONST_DOCKER_RESOURCE_IMAGES: Final[str] = "images"
CONST_DOCKER_RESOURCE_NETWORKS: Final[str] = "networks"
CONST_DOCKER_RESOURCE_VOLUMES: Final[str] = "volumes"
CONST_DOCKER_RESOURCE_REGISTRIES: Final[str] = "registries"
CONST_DOCKER_RESOURCES: Final[tuple[str, ...]] = (
    CONST_DOCKER_RESOURCE_CONTAINERS,
    CONST_DOCKER_RESOURCE_IMAGES,
    CONST_DOCKER_RESOURCE_NETWORKS,
    CONST_DOCKER_RESOURCE_VOLUMES,
    CONST_DOCKER_RESOURCE_REGISTRIES,
)
CONST_DOCKER_RESOURCE_LABELS: Final[dict[str, str]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: "Containers",
    CONST_DOCKER_RESOURCE_IMAGES: "Images",
    CONST_DOCKER_RESOURCE_NETWORKS: "Networks",
    CONST_DOCKER_RESOURCE_VOLUMES: "Volumes",
    CONST_DOCKER_RESOURCE_REGISTRIES: "Registries",
}
# Tab holding the streamed log pane. Not a data domain: it has no provider and is filled
# by selecting a pod rather than by the refresh cycle.
CONST_LOGS_TAB_ID: Final[str] = "tab-logs"

# ── W3C Trace Context ────────────────────────────────────────────────────────
# https://www.w3.org/TR/trace-context/
CONST_TRACEPARENT_VERSION: Final[str] = "00"
# Version "ff" is reserved by the specification and must never be accepted.
CONST_TRACEPARENT_INVALID_VERSION: Final[str] = "ff"
CONST_TRACE_ID_HEX_LENGTH: Final[int] = 32
CONST_SPAN_ID_HEX_LENGTH: Final[int] = 16
CONST_TRACE_FLAGS_HEX_LENGTH: Final[int] = 2
CONST_TRACE_FLAG_SAMPLED: Final[str] = "01"
CONST_TRACE_FLAG_NOT_SAMPLED: Final[str] = "00"
# HTTP headers are lowercase; process environment variables are uppercase. Using one
# spelling for both is what lets an injected value be shadowed by an inherited one.
CONST_TRACEPARENT_HEADER: Final[str] = "traceparent"
CONST_TRACESTATE_HEADER: Final[str] = "tracestate"
CONST_TRACEPARENT_ENV_VAR: Final[str] = "TRACEPARENT"
CONST_TRACESTATE_ENV_VAR: Final[str] = "TRACESTATE"
# The specification caps tracestate at 32 list members.
CONST_TRACESTATE_MAX_MEMBERS: Final[int] = 32

# ── SARIF (Static Analysis Results Interchange Format) ───────────────────────
# https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
CONST_SARIF_VERSION: Final[str] = "2.1.0"
CONST_SARIF_SCHEMA_URI: Final[str] = "https://json.schemastore.org/sarif-2.1.0.json"
# SARIF defines exactly these result levels; anything else is rejected by consumers.
CONST_SARIF_LEVEL_ERROR: Final[str] = "error"
CONST_SARIF_LEVEL_WARNING: Final[str] = "warning"
CONST_SARIF_LEVEL_NOTE: Final[str] = "note"
CONST_SARIF_LEVEL_NONE: Final[str] = "none"
CONST_SARIF_LEVELS: Final[frozenset[str]] = frozenset(
    {
        CONST_SARIF_LEVEL_ERROR,
        CONST_SARIF_LEVEL_WARNING,
        CONST_SARIF_LEVEL_NOTE,
        CONST_SARIF_LEVEL_NONE,
    }
)
# GitHub code scanning ranks by this property rather than by SARIF level, so both are
# emitted: the level for generic consumers, the score for GitHub's severity ordering.
CONST_SARIF_SECURITY_SEVERITY_PROPERTY: Final[str] = "security-severity"
# Fingerprint key. SARIF requires a versioned name so a later change to the scheme does
# not silently re-open every previously suppressed result.
CONST_SARIF_FINGERPRINT_KEY: Final[str] = "devopsCli/v1"

# ── Security Finding Taxonomy ────────────────────────────────────────────────
CONST_SEVERITY_CRITICAL: Final[str] = "CRITICAL"
CONST_SEVERITY_HIGH: Final[str] = "HIGH"
CONST_SEVERITY_MEDIUM: Final[str] = "MEDIUM"
CONST_SEVERITY_LOW: Final[str] = "LOW"
CONST_SEVERITY_INFO: Final[str] = "INFO"
# Ordered most severe first; the index doubles as the ranking key.
CONST_SEVERITY_ORDER: Final[tuple[str, ...]] = (
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_MEDIUM,
    CONST_SEVERITY_LOW,
    CONST_SEVERITY_INFO,
)
CONST_SEVERITY_TO_SARIF_LEVEL: Final[dict[str, str]] = {
    CONST_SEVERITY_CRITICAL: CONST_SARIF_LEVEL_ERROR,
    CONST_SEVERITY_HIGH: CONST_SARIF_LEVEL_ERROR,
    CONST_SEVERITY_MEDIUM: CONST_SARIF_LEVEL_WARNING,
    CONST_SEVERITY_LOW: CONST_SARIF_LEVEL_NOTE,
    CONST_SEVERITY_INFO: CONST_SARIF_LEVEL_NOTE,
}
# GitHub's documented banding: 9.0+ critical, 7.0+ high, 4.0+ medium, 0.1+ low.
CONST_SEVERITY_TO_SECURITY_SCORE: Final[dict[str, str]] = {
    CONST_SEVERITY_CRITICAL: "9.5",
    CONST_SEVERITY_HIGH: "7.5",
    CONST_SEVERITY_MEDIUM: "5.0",
    CONST_SEVERITY_LOW: "2.0",
    CONST_SEVERITY_INFO: "0.5",
}
# Severity vocabularies differ per scanner; these are the spellings actually emitted.
CONST_SEVERITY_ALIASES: Final[dict[str, str]] = {
    "CRITICAL": CONST_SEVERITY_CRITICAL,
    "BLOCKER": CONST_SEVERITY_CRITICAL,
    "HIGH": CONST_SEVERITY_HIGH,
    "ERROR": CONST_SEVERITY_HIGH,
    "MEDIUM": CONST_SEVERITY_MEDIUM,
    "MODERATE": CONST_SEVERITY_MEDIUM,
    "WARNING": CONST_SEVERITY_MEDIUM,
    "WARN": CONST_SEVERITY_MEDIUM,
    "LOW": CONST_SEVERITY_LOW,
    "MINOR": CONST_SEVERITY_LOW,
    "NOTE": CONST_SEVERITY_LOW,
    "INFO": CONST_SEVERITY_INFO,
    "INFORMATIONAL": CONST_SEVERITY_INFO,
    "UNKNOWN": CONST_SEVERITY_INFO,
    "NONE": CONST_SEVERITY_INFO,
}
CONST_SARIF_LEVEL_TO_SEVERITY: Final[dict[str, str]] = {
    CONST_SARIF_LEVEL_ERROR: CONST_SEVERITY_HIGH,
    CONST_SARIF_LEVEL_WARNING: CONST_SEVERITY_MEDIUM,
    CONST_SARIF_LEVEL_NOTE: CONST_SEVERITY_LOW,
    CONST_SARIF_LEVEL_NONE: CONST_SEVERITY_INFO,
}
# Depth limit for suppression policy inheritance, so a misconfigured chain fails with a
# clear error rather than recursing until the interpreter stops it.
CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH: Final[int] = 10

# ── OpenSSH known_hosts ──────────────────────────────────────────────────────
# Hashed host fields are written as |1|<base64 salt>|<base64 HMAC-SHA1 digest>.
CONST_KNOWN_HOSTS_HASH_PREFIX: Final[str] = "|1|"
CONST_KNOWN_HOSTS_MARKER_REVOKED: Final[str] = "@revoked"
CONST_KNOWN_HOSTS_MARKER_CERT_AUTHORITY: Final[str] = "@cert-authority"

# ── SSH Host Key Verification ────────────────────────────────────────────────
CONST_SSH_FINGERPRINT_PREFIX: Final[str] = "SHA256:"
# Host key algorithms accepted from a scan. Types outside this set are ignored rather than
# written to known_hosts, where an unusable entry silently breaks later connections.
CONST_SSH_HOST_KEY_TYPES: Final[frozenset[str]] = frozenset(
    {
        "ssh-ed25519",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "ssh-rsa",
        "rsa-sha2-256",
        "rsa-sha2-512",
    }
)
# GitHub publishes these at https://api.github.com/meta over TLS, so pinning them lets the
# SSH host key be verified against a channel that is already authenticated rather than
# trusting whatever answers the first connection. Refresh with `devops git host-keys`.
CONST_GITHUB_HOST_KEY_FINGERPRINTS: Final[frozenset[str]] = frozenset(
    {
        "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU",  # ssh-ed25519
        "SHA256:p2QAMXNIC1TJYWeIOttrVc98/R1BUFWu3/LiyKgUfQM",  # ecdsa-sha2-nistp256
        "SHA256:uNiVztksCsDhcc0u9e8BujQXVUpKZIDTMczCvj3tD2s",  # ssh-rsa
    }
)
CONST_GITHUB_META_URL: Final[str] = "https://api.github.com/meta"

# ── Issue Closure From Merged Pull Requests ──────────────────────────────────
# GitHub's closing keywords. A pull request body using any of these links the issue, but
# GitHub only acts on the link when the pull request merges into the DEFAULT branch, so a
# pull request targeting a release branch leaves its issue open indefinitely.
# https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue
CONST_ISSUE_CLOSING_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "close",
        "closes",
        "closed",
        "fix",
        "fixes",
        "fixed",
        "resolve",
        "resolves",
        "resolved",
    }
)
CONST_ISSUE_STATE_OPEN: Final[str] = "open"
CONST_ISSUE_STATE_CLOSED: Final[str] = "closed"
# Series listed in the telemetry panel. A Prometheus instance exposes thousands of metric
# names; rendering all of them costs more than it tells the reader.
CONST_TELEMETRY_PANEL_MAX_SERIES: Final[int] = 50

# ── Cluster-Native Service Addressing ────────────────────────────────────────
# A k8s:// URL names a Service rather than a host and port, so the same configuration
# resolves on every cluster without a port-forward:
#   k8s://<namespace>/<service>:<port>[/path]        backend speaks http
#   k8s+https://<namespace>/<service>:<port>[/path]  backend speaks https
CONST_K8S_URL_SCHEME: Final[str] = "k8s"
CONST_K8S_URL_SCHEME_TLS: Final[str] = "k8s+https"
CONST_K8S_URL_SCHEMES: Final[frozenset[str]] = frozenset(
    {CONST_K8S_URL_SCHEME, CONST_K8S_URL_SCHEME_TLS}
)
# The API server exposes every Service at this path, which is what removes the need for a
# local port: https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/
CONST_K8S_SERVICE_PROXY_TEMPLATE: Final[str] = (
    "/api/v1/namespaces/{namespace}/services/{target}/proxy"
)
# How `configure-urls` records endpoints. "nodeport" writes a reachable host and port,
# which is fast but cluster-specific; "proxy" writes k8s:// service addresses, which carry
# no host and therefore resolve on whichever cluster is active.
CONST_ADDRESSING_NODEPORT: Final[str] = "nodeport"
CONST_ADDRESSING_PROXY: Final[str] = "proxy"
CONST_ADDRESSING_MODES: Final[frozenset[str]] = frozenset(
    {CONST_ADDRESSING_NODEPORT, CONST_ADDRESSING_PROXY}
)
# Lines held between the stream reader and the renderer. Bounded so a producer faster than
# the terminal cannot grow it without limit; the log buffer is the retention mechanism.
CONST_LOG_STREAM_QUEUE_SIZE: Final[int] = 2000
