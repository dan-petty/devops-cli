"""Environment variable names mapped to config option keys."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config import options as opt

ENV_DEVOPS_CLI_CONFIG = "DEVOPS_CLI_CONFIG"

ENV_GITHUB_TOKEN = "DEVOPS_CLI_GITHUB_TOKEN"
ENV_GITHUB_DEFAULT_ORG = "DEVOPS_CLI_GITHUB_DEFAULT_ORG"
ENV_SSH_KEY_DIR = "DEVOPS_CLI_SSH_KEY_DIR"
ENV_SSH_KEY_PREFIX = "DEVOPS_CLI_SSH_KEY_PREFIX"
ENV_SSH_ROTATION_DAYS = "DEVOPS_CLI_SSH_ROTATION_DAYS"
ENV_REPOS_BASE_DIR = "DEVOPS_CLI_REPOS_BASE_DIR"
ENV_WORKSPACE_FILE = "DEVOPS_CLI_WORKSPACE_FILE"
ENV_GRAFANA_URL = "DEVOPS_CLI_GRAFANA_URL"
ENV_GRAFANA_TOKEN = "DEVOPS_CLI_GRAFANA_TOKEN"
ENV_PROMETHEUS_URL = "DEVOPS_CLI_PROMETHEUS_URL"
ENV_ARGOCD_URL = "DEVOPS_CLI_ARGOCD_URL"
ENV_ARGOCD_TOKEN = "DEVOPS_CLI_ARGOCD_TOKEN"
ENV_AI_PROVIDER = "DEVOPS_CLI_AI_PROVIDER"
ENV_AI_MODEL = "DEVOPS_CLI_AI_MODEL"
ENV_AI_OLLAMA_URLS = "DEVOPS_CLI_AI_OLLAMA_URLS"
ENV_AI_OLLAMA_MAX_PARALLEL = "DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL"
ENV_AI_API_BASE_URL = "DEVOPS_CLI_AI_API_BASE_URL"
ENV_AI_API_KEY = "DEVOPS_CLI_AI_API_KEY"
ENV_AI_REASONING_EFFORT = "DEVOPS_CLI_AI_REASONING_EFFORT"
ENV_AI_ALLOW_PRIVATE_NETWORK = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"
ENV_AI_MAX_RETRIES = "DEVOPS_CLI_AI_MAX_RETRIES"
ENV_AI_APPEND_CACHE = "DEVOPS_CLI_AI_APPEND_CACHE"

ENV_AI_TASK_CHAT_PROVIDER = "DEVOPS_CLI_AI_TASK_CHAT_PROVIDER"
ENV_AI_TASK_CHAT_MODEL = "DEVOPS_CLI_AI_TASK_CHAT_MODEL"
ENV_AI_TASK_CHAT_REASONING_EFFORT = "DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT"
ENV_AI_TASK_CHAT_OLLAMA_URLS = "DEVOPS_CLI_AI_TASK_CHAT_OLLAMA_URLS"
ENV_AI_TASK_METADATA_PROVIDER = "DEVOPS_CLI_AI_TASK_METADATA_PROVIDER"
ENV_AI_TASK_METADATA_MODEL = "DEVOPS_CLI_AI_TASK_METADATA_MODEL"
ENV_AI_TASK_METADATA_REASONING_EFFORT = "DEVOPS_CLI_AI_TASK_METADATA_REASONING_EFFORT"
ENV_AI_TASK_METADATA_OLLAMA_URLS = "DEVOPS_CLI_AI_TASK_METADATA_OLLAMA_URLS"
ENV_AI_TASK_ANALYSIS_PROVIDER = "DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER"
ENV_AI_TASK_ANALYSIS_MODEL = "DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL"
ENV_AI_TASK_ANALYSIS_REASONING_EFFORT = "DEVOPS_CLI_AI_TASK_ANALYSIS_REASONING_EFFORT"
ENV_AI_TASK_ANALYSIS_OLLAMA_URLS = "DEVOPS_CLI_AI_TASK_ANALYSIS_OLLAMA_URLS"
ENV_AI_TASK_COMPOSE_PROVIDER = "DEVOPS_CLI_AI_TASK_COMPOSE_PROVIDER"
ENV_AI_TASK_COMPOSE_MODEL = "DEVOPS_CLI_AI_TASK_COMPOSE_MODEL"
ENV_AI_TASK_COMPOSE_REASONING_EFFORT = "DEVOPS_CLI_AI_TASK_COMPOSE_REASONING_EFFORT"
ENV_AI_TASK_COMPOSE_OLLAMA_URLS = "DEVOPS_CLI_AI_TASK_COMPOSE_OLLAMA_URLS"
ENV_AI_TASK_EMBEDDING_PROVIDER = "DEVOPS_CLI_AI_TASK_EMBEDDING_PROVIDER"
ENV_AI_TASK_EMBEDDING_MODEL = "DEVOPS_CLI_AI_TASK_EMBEDDING_MODEL"
ENV_AI_TASK_EMBEDDING_REASONING_EFFORT = "DEVOPS_CLI_AI_TASK_EMBEDDING_REASONING_EFFORT"
ENV_AI_TASK_EMBEDDING_OLLAMA_URLS = "DEVOPS_CLI_AI_TASK_EMBEDDING_OLLAMA_URLS"

ENV_AI_RAG_ENABLED = "DEVOPS_CLI_AI_RAG_ENABLED"
ENV_AI_RAG_EMBEDDING_MODEL = "DEVOPS_CLI_AI_RAG_EMBEDDING_MODEL"
ENV_AI_RAG_EMBEDDING_URL = "DEVOPS_CLI_AI_RAG_EMBEDDING_URL"
ENV_AI_RAG_TOP_K = "DEVOPS_CLI_AI_RAG_TOP_K"
ENV_AI_RAG_SCORE_THRESHOLD = "DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD"

ENV_QDRANT_URL = "DEVOPS_CLI_QDRANT_URL"
ENV_QDRANT_API_KEY = "DEVOPS_CLI_QDRANT_API_KEY"
ENV_QDRANT_COLLECTION_PREFIX = "DEVOPS_CLI_QDRANT_COLLECTION_PREFIX"

# Data Storage & Artifact Path environment variables
ENV_DATA_DIR = "DEVOPS_CLI_DATA_DIR"
ENV_DATA_ANALYSIS_DIR = "DEVOPS_CLI_DATA_ANALYSIS_DIR"
ENV_DATA_REVIEWS_DIR = "DEVOPS_CLI_DATA_REVIEWS_DIR"
ENV_DATA_LOGS_DIR = "DEVOPS_CLI_DATA_LOGS_DIR"
ENV_DATA_MODELS_DIR = "DEVOPS_CLI_DATA_MODELS_DIR"
ENV_DATA_CACHE_DIR = "DEVOPS_CLI_DATA_CACHE_DIR"
ENV_DATA_BENCHMARKS_DIR = "DEVOPS_CLI_DATA_BENCHMARKS_DIR"
ENV_DATA_RAG_DIR = "DEVOPS_CLI_DATA_RAG_DIR"
ENV_DATA_TLS_DIR = "DEVOPS_CLI_DATA_TLS_DIR"
ENV_DATA_AUDIT_LOG_PATH = "DEVOPS_CLI_DATA_AUDIT_LOG_PATH"
ENV_DATA_FEEDBACK_DATASET_PATH = "DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH"

OPTION_TO_ENV_VAR: dict[str, str] = {
    opt.GITHUB_TOKEN: ENV_GITHUB_TOKEN,
    opt.GITHUB_DEFAULT_ORG: ENV_GITHUB_DEFAULT_ORG,
    opt.SSH_KEY_DIR: ENV_SSH_KEY_DIR,
    opt.SSH_KEY_PREFIX: ENV_SSH_KEY_PREFIX,
    opt.SSH_ROTATION_DAYS: ENV_SSH_ROTATION_DAYS,
    opt.REPOS_BASE_DIR: ENV_REPOS_BASE_DIR,
    opt.WORKSPACE_FILE: ENV_WORKSPACE_FILE,
    opt.GRAFANA_URL: ENV_GRAFANA_URL,
    opt.GRAFANA_TOKEN: ENV_GRAFANA_TOKEN,
    opt.PROMETHEUS_URL: ENV_PROMETHEUS_URL,
    opt.ARGOCD_URL: ENV_ARGOCD_URL,
    opt.ARGOCD_TOKEN: ENV_ARGOCD_TOKEN,
    opt.AI_PROVIDER: ENV_AI_PROVIDER,
    opt.AI_MODEL: ENV_AI_MODEL,
    opt.AI_OLLAMA_URLS: ENV_AI_OLLAMA_URLS,
    opt.AI_OLLAMA_MAX_PARALLEL: ENV_AI_OLLAMA_MAX_PARALLEL,
    opt.AI_API_BASE_URL: ENV_AI_API_BASE_URL,
    opt.AI_API_KEY: ENV_AI_API_KEY,
    opt.AI_REASONING_EFFORT: ENV_AI_REASONING_EFFORT,
    opt.AI_ALLOW_PRIVATE_NETWORK: ENV_AI_ALLOW_PRIVATE_NETWORK,
    opt.AI_MAX_RETRIES: ENV_AI_MAX_RETRIES,
    opt.AI_TASK_CHAT_PROVIDER: ENV_AI_TASK_CHAT_PROVIDER,
    opt.AI_TASK_CHAT_MODEL: ENV_AI_TASK_CHAT_MODEL,
    opt.AI_TASK_CHAT_REASONING_EFFORT: ENV_AI_TASK_CHAT_REASONING_EFFORT,
    opt.AI_TASK_CHAT_OLLAMA_URLS: ENV_AI_TASK_CHAT_OLLAMA_URLS,
    opt.AI_TASK_METADATA_PROVIDER: ENV_AI_TASK_METADATA_PROVIDER,
    opt.AI_TASK_METADATA_MODEL: ENV_AI_TASK_METADATA_MODEL,
    opt.AI_TASK_METADATA_REASONING_EFFORT: ENV_AI_TASK_METADATA_REASONING_EFFORT,
    opt.AI_TASK_METADATA_OLLAMA_URLS: ENV_AI_TASK_METADATA_OLLAMA_URLS,
    opt.AI_TASK_ANALYSIS_PROVIDER: ENV_AI_TASK_ANALYSIS_PROVIDER,
    opt.AI_TASK_ANALYSIS_MODEL: ENV_AI_TASK_ANALYSIS_MODEL,
    opt.AI_TASK_ANALYSIS_REASONING_EFFORT: ENV_AI_TASK_ANALYSIS_REASONING_EFFORT,
    opt.AI_TASK_ANALYSIS_OLLAMA_URLS: ENV_AI_TASK_ANALYSIS_OLLAMA_URLS,
    opt.AI_TASK_COMPOSE_PROVIDER: ENV_AI_TASK_COMPOSE_PROVIDER,
    opt.AI_TASK_COMPOSE_MODEL: ENV_AI_TASK_COMPOSE_MODEL,
    opt.AI_TASK_COMPOSE_REASONING_EFFORT: ENV_AI_TASK_COMPOSE_REASONING_EFFORT,
    opt.AI_TASK_COMPOSE_OLLAMA_URLS: ENV_AI_TASK_COMPOSE_OLLAMA_URLS,
    opt.AI_TASK_EMBEDDING_PROVIDER: ENV_AI_TASK_EMBEDDING_PROVIDER,
    opt.AI_TASK_EMBEDDING_MODEL: ENV_AI_TASK_EMBEDDING_MODEL,
    opt.AI_TASK_EMBEDDING_REASONING_EFFORT: ENV_AI_TASK_EMBEDDING_REASONING_EFFORT,
    opt.AI_TASK_EMBEDDING_OLLAMA_URLS: ENV_AI_TASK_EMBEDDING_OLLAMA_URLS,
    opt.AI_RAG_ENABLED: ENV_AI_RAG_ENABLED,
    opt.AI_RAG_EMBEDDING_MODEL: ENV_AI_RAG_EMBEDDING_MODEL,
    opt.AI_RAG_EMBEDDING_URL: ENV_AI_RAG_EMBEDDING_URL,
    opt.AI_RAG_TOP_K: ENV_AI_RAG_TOP_K,
    opt.AI_RAG_SCORE_THRESHOLD: ENV_AI_RAG_SCORE_THRESHOLD,
    opt.QDRANT_URL: ENV_QDRANT_URL,
    opt.QDRANT_API_KEY: ENV_QDRANT_API_KEY,
    opt.QDRANT_COLLECTION_PREFIX: ENV_QDRANT_COLLECTION_PREFIX,
    opt.DATA_DIR: ENV_DATA_DIR,
    opt.DATA_ANALYSIS_DIR: ENV_DATA_ANALYSIS_DIR,
    opt.DATA_REVIEWS_DIR: ENV_DATA_REVIEWS_DIR,
    opt.DATA_LOGS_DIR: ENV_DATA_LOGS_DIR,
    opt.DATA_MODELS_DIR: ENV_DATA_MODELS_DIR,
    opt.DATA_CACHE_DIR: ENV_DATA_CACHE_DIR,
    opt.DATA_BENCHMARKS_DIR: ENV_DATA_BENCHMARKS_DIR,
    opt.DATA_RAG_DIR: ENV_DATA_RAG_DIR,
    opt.DATA_TLS_DIR: ENV_DATA_TLS_DIR,
    opt.DATA_AUDIT_LOG_PATH: ENV_DATA_AUDIT_LOG_PATH,
    opt.DATA_FEEDBACK_DATASET_PATH: ENV_DATA_FEEDBACK_DATASET_PATH,
}

ENV_VAR_TO_OPTION: dict[str, str] = {v: k for k, v in OPTION_TO_ENV_VAR.items()}


class EnvVarSpec(BaseModel):
    """Metadata specification for a devops-cli environment variable."""

    model_config = ConfigDict(frozen=True)

    env_var: str
    option_key: str | None = None
    is_secret: bool = False
    description: str = ""

    def __init__(
        self,
        env_var: str,
        option_key: str | None = None,
        is_secret: bool = False,
        description: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            env_var=env_var,
            option_key=option_key,
            is_secret=is_secret,
            description=description,
            **kwargs,
        )


def env_var_for_option(option_key: str) -> str | None:
    """Return the mapped environment variable name for a config option key."""
    return OPTION_TO_ENV_VAR.get(option_key)


def get_all_env_var_specs() -> list[EnvVarSpec]:
    """Return all environment variable specifications available for configuration."""
    return [
        EnvVarSpec(
            ENV_DEVOPS_CLI_CONFIG,
            None,
            False,
            "Absolute path to project configuration file",
        ),
        EnvVarSpec(
            ENV_GITHUB_TOKEN,
            opt.GITHUB_TOKEN,
            True,
            "GitHub Personal Access Token (stored in OS keyring)",
        ),
        EnvVarSpec(
            ENV_GITHUB_DEFAULT_ORG,
            opt.GITHUB_DEFAULT_ORG,
            False,
            "Default GitHub organization",
        ),
        EnvVarSpec(
            ENV_SSH_KEY_DIR,
            opt.SSH_KEY_DIR,
            False,
            "Directory for SSH key pairs",
        ),
        EnvVarSpec(
            ENV_SSH_KEY_PREFIX,
            opt.SSH_KEY_PREFIX,
            False,
            "Prefix for generated SSH keys (defaults to devcontainer name or basename pwd)",
        ),
        EnvVarSpec(
            ENV_SSH_ROTATION_DAYS,
            opt.SSH_ROTATION_DAYS,
            False,
            "SSH key rotation interval in days",
        ),
        EnvVarSpec(
            ENV_REPOS_BASE_DIR,
            opt.REPOS_BASE_DIR,
            False,
            "Base directory for cloned repositories",
        ),
        EnvVarSpec(
            ENV_WORKSPACE_FILE,
            opt.WORKSPACE_FILE,
            False,
            "Path to VS Code workspace file",
        ),
        EnvVarSpec(
            ENV_GRAFANA_URL,
            opt.GRAFANA_URL,
            False,
            "Grafana service URL",
        ),
        EnvVarSpec(
            ENV_GRAFANA_TOKEN,
            opt.GRAFANA_TOKEN,
            True,
            "Grafana API token (stored in OS keyring)",
        ),
        EnvVarSpec(
            ENV_PROMETHEUS_URL,
            opt.PROMETHEUS_URL,
            False,
            "Prometheus service URL",
        ),
        EnvVarSpec(
            ENV_ARGOCD_URL,
            opt.ARGOCD_URL,
            False,
            "ArgoCD service URL",
        ),
        EnvVarSpec(
            ENV_ARGOCD_TOKEN,
            opt.ARGOCD_TOKEN,
            True,
            "ArgoCD API token (stored in OS keyring)",
        ),
        EnvVarSpec(
            ENV_AI_PROVIDER,
            opt.AI_PROVIDER,
            False,
            "AI provider (ollama | claude | copilot | openai)",
        ),
        EnvVarSpec(
            ENV_AI_MODEL,
            opt.AI_MODEL,
            False,
            "Default AI model name",
        ),
        EnvVarSpec(
            ENV_AI_OLLAMA_URLS,
            opt.AI_OLLAMA_URLS,
            False,
            "Ollama service URLs (comma-separated)",
        ),
        EnvVarSpec(
            ENV_AI_OLLAMA_MAX_PARALLEL,
            opt.AI_OLLAMA_MAX_PARALLEL,
            False,
            "Maximum parallel requests per Ollama host",
        ),
        EnvVarSpec(
            ENV_AI_API_BASE_URL,
            opt.AI_API_BASE_URL,
            False,
            "AI API base URL",
        ),
        EnvVarSpec(
            ENV_AI_API_KEY,
            opt.AI_API_KEY,
            True,
            "AI API key (stored in OS keyring)",
        ),
        EnvVarSpec(
            ENV_AI_REASONING_EFFORT,
            opt.AI_REASONING_EFFORT,
            False,
            "AI reasoning effort level (low | medium | high)",
        ),
        EnvVarSpec(
            ENV_AI_ALLOW_PRIVATE_NETWORK,
            opt.AI_ALLOW_PRIVATE_NETWORK,
            False,
            "Permit private-IP network targets",
        ),
        EnvVarSpec(
            ENV_AI_MAX_RETRIES,
            opt.AI_MAX_RETRIES,
            False,
            "Maximum retry count for AI requests upon response validation failure",
        ),
        EnvVarSpec(
            ENV_AI_TASK_CHAT_PROVIDER,
            opt.AI_TASK_CHAT_PROVIDER,
            False,
            "AI provider override for chat task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_CHAT_MODEL,
            opt.AI_TASK_CHAT_MODEL,
            False,
            "AI model override for chat task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_CHAT_OLLAMA_URLS,
            opt.AI_TASK_CHAT_OLLAMA_URLS,
            False,
            "Ollama URLs override for chat task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_METADATA_PROVIDER,
            opt.AI_TASK_METADATA_PROVIDER,
            False,
            "AI provider override for metadata task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_METADATA_MODEL,
            opt.AI_TASK_METADATA_MODEL,
            False,
            "AI model override for metadata task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_METADATA_OLLAMA_URLS,
            opt.AI_TASK_METADATA_OLLAMA_URLS,
            False,
            "Ollama URLs override for metadata task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_ANALYSIS_PROVIDER,
            opt.AI_TASK_ANALYSIS_PROVIDER,
            False,
            "AI provider override for analysis task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_ANALYSIS_MODEL,
            opt.AI_TASK_ANALYSIS_MODEL,
            False,
            "AI model override for analysis task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_ANALYSIS_OLLAMA_URLS,
            opt.AI_TASK_ANALYSIS_OLLAMA_URLS,
            False,
            "Ollama URLs override for analysis task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_COMPOSE_PROVIDER,
            opt.AI_TASK_COMPOSE_PROVIDER,
            False,
            "AI provider override for compose task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_COMPOSE_MODEL,
            opt.AI_TASK_COMPOSE_MODEL,
            False,
            "AI model override for compose task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_COMPOSE_OLLAMA_URLS,
            opt.AI_TASK_COMPOSE_OLLAMA_URLS,
            False,
            "Ollama URLs override for compose task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_EMBEDDING_PROVIDER,
            opt.AI_TASK_EMBEDDING_PROVIDER,
            False,
            "AI provider override for embedding generation task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_EMBEDDING_MODEL,
            opt.AI_TASK_EMBEDDING_MODEL,
            False,
            "AI model override for embedding generation task",
        ),
        EnvVarSpec(
            ENV_AI_TASK_EMBEDDING_OLLAMA_URLS,
            opt.AI_TASK_EMBEDDING_OLLAMA_URLS,
            False,
            "Ollama URLs override for embedding generation task",
        ),
        EnvVarSpec(
            ENV_AI_RAG_EMBEDDING_URL,
            opt.AI_RAG_EMBEDDING_URL,
            False,
            "Dedicated endpoint URL for RAG dense vector embedding generation (e.g. http://workhorse.lan:11434)",
        ),
        EnvVarSpec(
            ENV_QDRANT_URL,
            opt.QDRANT_URL,
            False,
            "Qdrant vector database server URL",
        ),
        EnvVarSpec(
            ENV_QDRANT_API_KEY,
            opt.QDRANT_API_KEY,
            True,
            "Qdrant API key (stored in OS keyring)",
        ),
        EnvVarSpec(
            ENV_QDRANT_COLLECTION_PREFIX,
            opt.QDRANT_COLLECTION_PREFIX,
            False,
            "Prefix for Qdrant collection names",
        ),
        EnvVarSpec(
            ENV_DATA_DIR,
            opt.DATA_DIR,
            False,
            "Root data directory for local reviews, cache, logs, and artifacts (default: ./.data)",
        ),
        EnvVarSpec(
            ENV_DATA_ANALYSIS_DIR,
            opt.DATA_ANALYSIS_DIR,
            False,
            "Storage directory for pre-analysis metadata JSON files",
        ),
        EnvVarSpec(
            ENV_DATA_REVIEWS_DIR,
            opt.DATA_REVIEWS_DIR,
            False,
            "Storage directory for review session finding reports and artifacts",
        ),
        EnvVarSpec(
            ENV_DATA_LOGS_DIR,
            opt.DATA_LOGS_DIR,
            False,
            "Storage directory for CLI execution and SIEM audit logs",
        ),
        EnvVarSpec(
            ENV_DATA_MODELS_DIR,
            opt.DATA_MODELS_DIR,
            False,
            "Storage directory for local model checkpoints and weights",
        ),
        EnvVarSpec(
            ENV_DATA_CACHE_DIR,
            opt.DATA_CACHE_DIR,
            False,
            "Storage directory for local response and retrieval cache",
        ),
        EnvVarSpec(
            ENV_DATA_BENCHMARKS_DIR,
            opt.DATA_BENCHMARKS_DIR,
            False,
            "Storage directory for benchmark test runs and embedding leaderboard reports",
        ),
        EnvVarSpec(
            ENV_DATA_RAG_DIR,
            opt.DATA_RAG_DIR,
            False,
            "Storage directory for local vector embedding index cache and retrieval data",
        ),
        EnvVarSpec(
            ENV_DATA_TLS_DIR,
            opt.DATA_TLS_DIR,
            False,
            "Storage directory for generated local CA and TLS certificates",
        ),
        EnvVarSpec(
            ENV_DATA_AUDIT_LOG_PATH,
            opt.DATA_AUDIT_LOG_PATH,
            False,
            "Path to structured audit JSONL log file",
        ),
        EnvVarSpec(
            ENV_DATA_FEEDBACK_DATASET_PATH,
            opt.DATA_FEEDBACK_DATASET_PATH,
            False,
            "Path to feedback fine-tuning dataset JSONL file",
        ),
    ]
