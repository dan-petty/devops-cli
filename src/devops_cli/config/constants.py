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
CONST_README_FILENAME = "README.md"
CONST_INIT_PY_PATH = Path("src/devops_cli/__init__.py")
CONST_CURRENT_DIR = Path(".")
CONST_ROOT_DIR = Path("/")
CONST_SRC_DIR_NAME = "src"
CONST_DOCS_DIR_NAME = "docs"
CONST_DOCS_DIR_PATH = Path(CONST_DOCS_DIR_NAME)
CONST_TESTS_DIR_NAME = "tests"
CONST_TESTS_DIR_PATH = Path(CONST_TESTS_DIR_NAME)
CONST_VSCODE_DIR_NAME = ".vscode"
CONST_MCP_JSON_NAME = "mcp.json"
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
CONST_ERROR_CODE_VALKEY = "VALKEY_ERROR"
CONST_ERROR_CODE_DOCKER_SANDBOX = "DOCKER_SANDBOX_ERROR"
CONST_ERROR_CODE_K8S = "K8S_ERROR"
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
