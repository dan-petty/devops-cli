"""Canonical config option keys and secret storage mapping."""

from __future__ import annotations

GITHUB_TOKEN = "github.token"
GITHUB_DEFAULT_ORG = "github.default_org"
SSH_KEY_DIR = "ssh.key_dir"
SSH_ROTATION_DAYS = "ssh.rotation_days"
REPOS_BASE_DIR = "repos.base_dir"
WORKSPACE_FILE = "workspace.file"
GRAFANA_URL = "grafana.url"
GRAFANA_TOKEN = "grafana.token"
PROMETHEUS_URL = "prometheus.url"
ARGOCD_URL = "argocd.url"
ARGOCD_TOKEN = "argocd.token"
AI_PROVIDER = "ai.provider"
AI_MODEL = "ai.model"
AI_OLLAMA_URL = "ai.ollama_url"
AI_API_BASE_URL = "ai.api_base_url"
AI_API_KEY = "ai.api_key"

CONFIG_OPTIONS: tuple[str, ...] = (
    GITHUB_TOKEN,
    GITHUB_DEFAULT_ORG,
    SSH_KEY_DIR,
    SSH_ROTATION_DAYS,
    REPOS_BASE_DIR,
    WORKSPACE_FILE,
    GRAFANA_URL,
    GRAFANA_TOKEN,
    PROMETHEUS_URL,
    ARGOCD_URL,
    ARGOCD_TOKEN,
    AI_PROVIDER,
    AI_MODEL,
    AI_OLLAMA_URL,
    AI_API_BASE_URL,
    AI_API_KEY,
)

SECRET_CONFIG_OPTIONS: frozenset[str] = frozenset(
    {GITHUB_TOKEN, GRAFANA_TOKEN, ARGOCD_TOKEN, AI_API_KEY}
)

KEYRING_KEYS: dict[str, str] = {
    GITHUB_TOKEN: "github_token",
    GRAFANA_TOKEN: "grafana_token",
    ARGOCD_TOKEN: "argocd_token",
    AI_API_KEY: "ai_api_key",
}
