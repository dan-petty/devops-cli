"""Configuration defaults and environment variable names."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_REVIEW_TIMEOUT_SECONDS, CONST_URL_OLLAMA_LOCALHOST

# Defaults
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_WORKSPACE_FILE = Path(".code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = CONST_URL_OLLAMA_LOCALHOST
DEFAULT_PYTHON_VERSION = "3.14"

# HTTP timeouts
HTTP_CONNECT_TIMEOUT_SECONDS = 1.0
HTTP_READ_TIMEOUT_SECONDS = 30.0
HTTP_WRITE_TIMEOUT_SECONDS = 30.0
HTTP_POOL_TIMEOUT_SECONDS = 5.0

# Review command defaults
DEFAULT_REVIEW_TIMEOUT_SECONDS = CONST_REVIEW_TIMEOUT_SECONDS
