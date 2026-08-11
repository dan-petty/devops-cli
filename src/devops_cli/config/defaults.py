"""Configuration defaults and consolidated high timeout values."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_REVIEW_TIMEOUT_SECONDS, CONST_URL_OLLAMA_LOCALHOST

# ── General Defaults ──────────────────────────────────────────────────────────
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_WORKSPACE_FILE = Path(".code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "gemma4:26b"
DEFAULT_OLLAMA_URLS: tuple[str, ...] = (CONST_URL_OLLAMA_LOCALHOST,)
DEFAULT_PYTHON_VERSION = "3.14"

# NOTE (Design Justification - AGENTS.md §4 & README.md): High default timeouts are intentional
# to accommodate local LLM inference (CPU/GPU Ollama), corporate proxy delays, and minikube setup.
DEFAULT_REVIEW_TIMEOUT_SECONDS: float = CONST_REVIEW_TIMEOUT_SECONDS  # 3600.0s (1 hour)
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes (kubectl, helm, minikube, git, gh)
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 3600.0  # 1 hour (API requests & downloads)
DEFAULT_DNS_TIMEOUT_SECONDS: float = 15.0  # 15 seconds (socket DNS resolution)

# ── Consolidated Aliases & Sub-keys ───────────────────────────────────────────
# NOTE (Design Justification - AGENTS.md §4): Short/fast aliases map to main subprocess timeout
# to guarantee uniform bounds across all subcommand subprocess invocations.
DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS

HTTP_CONNECT_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_READ_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_WRITE_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_POOL_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS

DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_HTTP_LONG_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_HTTP_DOWNLOAD_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_GH_AUTH_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_KEYRING_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
