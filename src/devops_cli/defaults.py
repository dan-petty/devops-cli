"""Centralized defaults, static values, and environment variable names."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "devops-cli"

# CLI behavior
HELP_OPTION_NAMES = ("-h", "--help")

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.yaml"

# Keyring
KEYRING_SERVICE = APP_NAME

# Environment variables
ENV_GITHUB_TOKEN = "DEVOPS_CLI_GITHUB_TOKEN"
ENV_GRAFANA_TOKEN = "DEVOPS_CLI_GRAFANA_TOKEN"
ENV_ARGOCD_TOKEN = "DEVOPS_CLI_ARGOCD_TOKEN"
ENV_AI_API_KEY = "DEVOPS_CLI_AI_API_KEY"

# Defaults
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_WORKSPACE_FILE = Path("devops.code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# HTTP timeouts
HTTP_CONNECT_TIMEOUT_SECONDS = 1.0
HTTP_READ_TIMEOUT_SECONDS = 30.0
HTTP_WRITE_TIMEOUT_SECONDS = 30.0
HTTP_POOL_TIMEOUT_SECONDS = 5.0
