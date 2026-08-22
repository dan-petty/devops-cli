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
AI_OLLAMA_URLS = "ai.ollama_urls"
AI_OLLAMA_MAX_PARALLEL = "ai.ollama_max_parallel"
AI_API_BASE_URL = "ai.api_base_url"
AI_API_KEY = "ai.api_key"
AI_ALLOW_PRIVATE_NETWORK = "ai.allow_private_network"
AI_MAX_RETRIES = "ai.max_retries"

# Per-task model overrides (each falls back to the base ai.* values if unset)
AI_TASK_CHAT_PROVIDER = "ai.tasks.chat.provider"
AI_TASK_CHAT_MODEL = "ai.tasks.chat.model"
AI_TASK_CHAT_OLLAMA_URLS = "ai.tasks.chat.ollama_urls"
AI_TASK_METADATA_PROVIDER = "ai.tasks.metadata.provider"
AI_TASK_METADATA_MODEL = "ai.tasks.metadata.model"
AI_TASK_METADATA_OLLAMA_URLS = "ai.tasks.metadata.ollama_urls"
AI_TASK_ANALYSIS_PROVIDER = "ai.tasks.analysis.provider"
AI_TASK_ANALYSIS_MODEL = "ai.tasks.analysis.model"
AI_TASK_ANALYSIS_OLLAMA_URLS = "ai.tasks.analysis.ollama_urls"
AI_TASK_COMPOSE_PROVIDER = "ai.tasks.compose.provider"
AI_TASK_COMPOSE_MODEL = "ai.tasks.compose.model"
AI_TASK_COMPOSE_OLLAMA_URLS = "ai.tasks.compose.ollama_urls"

# v0.1.1 Feature Flags
FEATURE_PR_INLINE_COMMENTS = "features.pr_inline_comments"
FEATURE_CUSTOM_PERSONAS = "features.custom_personas"
FEATURE_HEADLESS_AUTH = "features.headless_auth"

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
    AI_OLLAMA_URLS,
    AI_OLLAMA_MAX_PARALLEL,
    AI_API_BASE_URL,
    AI_API_KEY,
    AI_ALLOW_PRIVATE_NETWORK,
    AI_MAX_RETRIES,
    AI_TASK_CHAT_PROVIDER,
    AI_TASK_CHAT_MODEL,
    AI_TASK_CHAT_OLLAMA_URLS,
    AI_TASK_METADATA_PROVIDER,
    AI_TASK_METADATA_MODEL,
    AI_TASK_METADATA_OLLAMA_URLS,
    AI_TASK_ANALYSIS_PROVIDER,
    AI_TASK_ANALYSIS_MODEL,
    AI_TASK_ANALYSIS_OLLAMA_URLS,
    AI_TASK_COMPOSE_PROVIDER,
    AI_TASK_COMPOSE_MODEL,
    AI_TASK_COMPOSE_OLLAMA_URLS,
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
