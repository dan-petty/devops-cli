"""Non-configurable constants used across the CLI."""

from __future__ import annotations

from pathlib import Path

CONST_APP_NAME = "devops-cli"
CONST_HELP_OPTION_NAMES = ("-h", "--help")
CONST_CONFIG_DIR = Path.home() / ".config" / CONST_APP_NAME
CONST_CONFIG_PATH = CONST_CONFIG_DIR / "config.yaml"
CONST_KEYRING_SERVICE = CONST_APP_NAME

CONST_VSCODE_WORKSPACE_FILE = Path(".code-workspace")
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
CONST_VSCODE_CLI = "code"
CONST_GITHUB_HOST = "github.com"
CONST_URL_SCHEME_HTTP = "http://"
CONST_URL_SCHEME_HTTPS = "https://"
CONST_GITHUB_SSH_PREFIX = "git@github.com:"
CONST_GITHUB_SSH_URL_PREFIX = "ssh://git@github.com/"
CONST_GITHUB_HTTP_PREFIX = "http://github.com/"
CONST_GITHUB_HTTPS_PREFIX = "https://github.com/"
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
CONST_GITHUB_REPO_SUFFIX = ".git"
CONST_AGENTS_MD_FILENAME = "AGENTS.md"
CONST_PROJECT_CONFIG_FILENAME = "config.yaml"
CONST_PROJECT_CONFIG_ENV = "DEVOPS_CLI_CONFIG"  # absolute path overrides CWD lookup
CONST_DATA_DIR = Path(".data")
CONST_DEVCONTAINER_DIR_NAME = ".devcontainer"
CONST_DEVCONTAINER_JSON_NAME = "devcontainer.json"
CONST_DEVCONTAINER_POST_CREATE_NAME = "postCreate.sh"
CONST_DEVCONTAINER_JSON_PATH = Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_JSON_NAME
CONST_DEVCONTAINER_POST_CREATE_PATH = (
    Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_POST_CREATE_NAME
)
CONST_DEVCONTAINER_IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/python:"
CONST_ENTITY_SEPARATOR = "/"

CONST_PERM_DIR = 0o700
CONST_PERM_PRIVATE_KEY = 0o600
CONST_PERM_PUBLIC_KEY = 0o644
CONST_PERM_EXEC = 0o755

CONST_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

CONST_REVIEW_MAX_DIFF_CHARS = 24000
CONST_REVIEW_WINDOW_SIZE_FACTOR = 0.8
CONST_REVIEW_OVERLAP_FACTOR = 0.1
CONST_REVIEW_TIMEOUT_SECONDS = 1200
# Exact filenames excluded from review regardless of .gitignore status
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

CONST_DEFAULT_AI_MAX_RETRIES = 2

CONST_DEFAULT_TOOL_READ_MAX_BYTES: int = 4000
CONST_DEFAULT_TOOL_MAX_BYTES_LIMIT: int = 5_000_000
CONST_DEFAULT_TOOL_DIFF_MAX_CHARS: int = 4000
CONST_DEFAULT_TOOL_MAX_FILES: int = 100
CONST_DEFAULT_TOOL_MAX_SEARCH_MATCHES: int = 50
CONST_DEFAULT_TOOL_BUFFER_CHUNK_SIZE: int = 65536
CONST_DEFAULT_AGENT_MAX_TURNS: int = 5
CONST_DEFAULT_MCP_SERVER_PORT: int = 8000
