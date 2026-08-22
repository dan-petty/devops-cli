"""Non-configurable constants used across the CLI."""

from __future__ import annotations

import re
from pathlib import Path

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

# ── Data Directories & Artifact Paths ─────────────────────────────────────────
CONST_DATA_DIR = Path(".data")
CONST_ANALYSIS_DIR_NAME = "analysis"
CONST_REVIEWS_DIR_NAME = "reviews"
CONST_LOGS_DIR_NAME = "logs"
CONST_MODELS_DIR_NAME = "models"
CONST_AUDIT_LOG_NAME = "audit.jsonl"
CONST_FEEDBACK_DATASET_NAME = "feedback_dataset.jsonl"

CONST_ANALYSIS_DATA_DIR = CONST_DATA_DIR / CONST_ANALYSIS_DIR_NAME
CONST_REVIEWS_DATA_DIR = CONST_DATA_DIR / CONST_REVIEWS_DIR_NAME
CONST_LOGS_DATA_DIR = CONST_DATA_DIR / CONST_LOGS_DIR_NAME
CONST_MODELS_DATA_DIR = CONST_DATA_DIR / CONST_MODELS_DIR_NAME
CONST_AUDIT_LOG_PATH = CONST_LOGS_DATA_DIR / CONST_AUDIT_LOG_NAME
CONST_FEEDBACK_DATASET_PATH = CONST_DATA_DIR / CONST_FEEDBACK_DATASET_NAME

# ── TLS & Cryptographic Certificates ──────────────────────────────────────────
CONST_TLS_DIR_NAME = "tls"
CONST_TLS_DATA_DIR = CONST_DATA_DIR / CONST_TLS_DIR_NAME
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
CONST_GITIGNORE_DIRS = (
    ".venv",
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv",
    ".data",
)
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

CONST_PORT_ARGOCD = 8080
CONST_PORT_GRAFANA_LOCAL = 8030
CONST_PORT_GRAFANA = 3000
CONST_PORT_PROMETHEUS_LOCAL = 8090
CONST_PORT_PROMETHEUS = 9090
CONST_PORT_OLLAMA = 11434
CONST_PORT_OPEN_WEBUI = 8080
CONST_PORT_QDRANT = 6333
CONST_PORT_VALKEY = 6379

# ── File Permissions ──────────────────────────────────────────────────────────
CONST_PERM_DIR = 0o700
CONST_PERM_PRIVATE_KEY = 0o600
CONST_PERM_PUBLIC_KEY = 0o644
CONST_PERM_EXEC = 0o755

CONST_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

# ── Code Review & Analysis ────────────────────────────────────────────────────
CONST_REVIEW_MAX_DIFF_CHARS = 24000
CONST_REVIEW_WINDOW_SIZE_FACTOR = 0.8
CONST_REVIEW_OVERLAP_FACTOR = 0.1
CONST_REVIEW_TIMEOUT_SECONDS = 1200
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
CONST_STATUS_MITIGATED = "MITIGATED"

CONST_RECOMMENDATION_APPROVE = "APPROVE"
CONST_RECOMMENDATION_REQUEST_CHANGES = "REQUEST CHANGES"
CONST_RECOMMENDATION_BLOCK = "BLOCK"

# ── GitHub CLI & Pull Requests ────────────────────────────────────────────────
CONST_GH_CLI = "gh"
CONST_BRANCH_PREFIXES: tuple[str, ...] = (
    "feat/",
    "fix/",
    "docs/",
    "chore/",
    "refactor/",
    "release/",
)
