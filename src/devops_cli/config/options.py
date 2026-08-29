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
AI_REASONING_EFFORT = "ai.reasoning_effort"
AI_ALLOW_PRIVATE_NETWORK = "ai.allow_private_network"
AI_MAX_RETRIES = "ai.max_retries"

# Per-task model overrides (each falls back to the base ai.* values if unset)
AI_TASK_CHAT_PROVIDER = "ai.tasks.chat.provider"
AI_TASK_CHAT_MODEL = "ai.tasks.chat.model"
AI_TASK_CHAT_REASONING_EFFORT = "ai.tasks.chat.reasoning_effort"
AI_TASK_CHAT_OLLAMA_URLS = "ai.tasks.chat.ollama_urls"
AI_TASK_METADATA_PROVIDER = "ai.tasks.metadata.provider"
AI_TASK_METADATA_MODEL = "ai.tasks.metadata.model"
AI_TASK_METADATA_REASONING_EFFORT = "ai.tasks.metadata.reasoning_effort"
AI_TASK_METADATA_OLLAMA_URLS = "ai.tasks.metadata.ollama_urls"
AI_TASK_ANALYSIS_PROVIDER = "ai.tasks.analysis.provider"
AI_TASK_ANALYSIS_MODEL = "ai.tasks.analysis.model"
AI_TASK_ANALYSIS_REASONING_EFFORT = "ai.tasks.analysis.reasoning_effort"
AI_TASK_ANALYSIS_OLLAMA_URLS = "ai.tasks.analysis.ollama_urls"
AI_TASK_COMPOSE_PROVIDER = "ai.tasks.compose.provider"
AI_TASK_COMPOSE_MODEL = "ai.tasks.compose.model"
AI_TASK_COMPOSE_REASONING_EFFORT = "ai.tasks.compose.reasoning_effort"
AI_TASK_COMPOSE_OLLAMA_URLS = "ai.tasks.compose.ollama_urls"

# RAG & Semantic Retrieval settings
AI_RAG_ENABLED = "ai.rag.enabled"
AI_RAG_EMBEDDING_MODEL = "ai.rag.embedding_model"
AI_RAG_TOP_K = "ai.rag.top_k"
AI_RAG_SCORE_THRESHOLD = "ai.rag.score_threshold"

# Data Storage & Artifact Paths
DATA_DIR = "data.dir"
DATA_ANALYSIS_DIR = "data.analysis_dir"
DATA_REVIEWS_DIR = "data.reviews_dir"
DATA_LOGS_DIR = "data.logs_dir"
DATA_MODELS_DIR = "data.models_dir"
DATA_CACHE_DIR = "data.cache_dir"
DATA_BENCHMARKS_DIR = "data.benchmarks_dir"
DATA_RAG_DIR = "data.rag_dir"
DATA_TLS_DIR = "data.tls_dir"
DATA_AUDIT_LOG_PATH = "data.audit_log_path"
DATA_FEEDBACK_DATASET_PATH = "data.feedback_dataset_path"

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
    AI_REASONING_EFFORT,
    AI_ALLOW_PRIVATE_NETWORK,
    AI_MAX_RETRIES,
    AI_TASK_CHAT_PROVIDER,
    AI_TASK_CHAT_MODEL,
    AI_TASK_CHAT_REASONING_EFFORT,
    AI_TASK_CHAT_OLLAMA_URLS,
    AI_TASK_METADATA_PROVIDER,
    AI_TASK_METADATA_MODEL,
    AI_TASK_METADATA_REASONING_EFFORT,
    AI_TASK_METADATA_OLLAMA_URLS,
    AI_TASK_ANALYSIS_PROVIDER,
    AI_TASK_ANALYSIS_MODEL,
    AI_TASK_ANALYSIS_REASONING_EFFORT,
    AI_TASK_ANALYSIS_OLLAMA_URLS,
    AI_TASK_COMPOSE_PROVIDER,
    AI_TASK_COMPOSE_MODEL,
    AI_TASK_COMPOSE_REASONING_EFFORT,
    AI_TASK_COMPOSE_OLLAMA_URLS,
    AI_RAG_ENABLED,
    AI_RAG_EMBEDDING_MODEL,
    AI_RAG_TOP_K,
    AI_RAG_SCORE_THRESHOLD,
    DATA_DIR,
    DATA_ANALYSIS_DIR,
    DATA_REVIEWS_DIR,
    DATA_LOGS_DIR,
    DATA_MODELS_DIR,
    DATA_CACHE_DIR,
    DATA_BENCHMARKS_DIR,
    DATA_RAG_DIR,
    DATA_TLS_DIR,
    DATA_AUDIT_LOG_PATH,
    DATA_FEEDBACK_DATASET_PATH,
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
