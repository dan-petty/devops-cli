"""Configuration defaults and consolidated high timeout values."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from devops_cli.config.constants import (
    CONST_ANALYSIS_DIR_NAME,
    CONST_AUDIT_LOG_NAME,
    CONST_BENCHMARKS_DIR_NAME,
    CONST_CACHE_DIR_NAME,
    CONST_CONFIG_DIR,
    CONST_DOCS_DIR_PATH,
    CONST_FEEDBACK_DATASET_NAME,
    CONST_INDEX_CACHE_FILENAME,
    CONST_LLM_CACHE_DIR_NAME,
    CONST_LOGS_DIR_NAME,
    CONST_MODELS_DIR_NAME,
    CONST_RAG_DIR_NAME,
    CONST_REVIEWS_DIR_NAME,
    CONST_TLS_DIR_NAME,
    CONST_URL_OLLAMA_LOCALHOST,
)

# ── Data Directories & Artifact Default Paths ─────────────────────────────────
DEFAULT_DATA_DIR = Path(".data")
DEFAULT_ANALYSIS_DATA_DIR = DEFAULT_DATA_DIR / CONST_ANALYSIS_DIR_NAME
DEFAULT_REVIEWS_DATA_DIR = DEFAULT_DATA_DIR / CONST_REVIEWS_DIR_NAME
DEFAULT_LOGS_DATA_DIR = DEFAULT_DATA_DIR / CONST_LOGS_DIR_NAME
DEFAULT_MODELS_DATA_DIR = DEFAULT_DATA_DIR / CONST_MODELS_DIR_NAME
DEFAULT_CACHE_DATA_DIR = DEFAULT_DATA_DIR / CONST_CACHE_DIR_NAME
DEFAULT_LLM_CACHE_DATA_DIR = DEFAULT_CACHE_DATA_DIR / CONST_LLM_CACHE_DIR_NAME
DEFAULT_BENCHMARKS_DATA_DIR = DEFAULT_DATA_DIR / CONST_BENCHMARKS_DIR_NAME
DEFAULT_AUDIT_LOG_PATH = DEFAULT_LOGS_DATA_DIR / CONST_AUDIT_LOG_NAME
DEFAULT_FEEDBACK_DATASET_PATH = DEFAULT_DATA_DIR / CONST_FEEDBACK_DATASET_NAME
DEFAULT_TLS_DATA_DIR = DEFAULT_DATA_DIR / CONST_TLS_DIR_NAME
DEFAULT_RAG_DATA_DIR = DEFAULT_DATA_DIR / CONST_RAG_DIR_NAME
DEFAULT_RAG_INDEX_CACHE_PATH = DEFAULT_RAG_DATA_DIR / CONST_INDEX_CACHE_FILENAME

# ── General Defaults ──────────────────────────────────────────────────────────
DEFAULT_LOCAL_BIN_DIR = Path.home() / ".local" / "bin"
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_KEY_PREFIX: str | None = None
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_DOCS_DIR = CONST_DOCS_DIR_PATH
DEFAULT_GRAFANA_DASHBOARDS_DIR = Path("k8s/monitoring/dashboards")
DEFAULT_WORKSPACE_FILE = Path(".code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "gemma4:26b"
DEFAULT_AI_REASONING_EFFORT: str | None = None
DEFAULT_AI_TEMPERATURE: float = 0.1
DEFAULT_AI_TOP_P: float = 0.95
DEFAULT_AI_CONTEXT_WINDOW: int = 32768
DEFAULT_AI_MAX_CONTEXT_WINDOW: int = 131072
DEFAULT_OLLAMA_URLS: tuple[str, ...] = (CONST_URL_OLLAMA_LOCALHOST,)
DEFAULT_OLLAMA_MAX_PARALLEL: int = 2
DEFAULT_AI_MAX_RETRIES: int = 2
DEFAULT_LLM_CACHE_ENABLED: bool = True
DEFAULT_LLM_CACHE_TTL_SECONDS: int = 86400 * 7  # 7 days
DEFAULT_LLM_CACHE_MAX_ENTRIES: int = 1000
DEFAULT_PYTHON_VERSION: str = "3.14"
DEFAULT_BUNDLE_MODELS: tuple[str, ...] = ("qwen2.5-coder:7b", "llama3.1:8b")
DEFAULT_PR_STATE = "open"
DEFAULT_MAX_CONTEXT_TOKENS: int = 32768
DEFAULT_DIFF_CHUNK_BUDGET: int = 32768
DEFAULT_SEMGREP_CONFIG: str = "p/default"

# ── Benchmark Defaults ────────────────────────────────────────────────────────
DEFAULT_BENCHMARK_CONCURRENCY: int = 4
DEFAULT_BENCHMARK_FORMAT: str = "table"
DEFAULT_BENCHMARK_SAMPLES: int = 5
DEFAULT_BENCHMARK_TYPE: str = "auto"
DEFAULT_EMBEDDING_BENCHMARK_MODELS: tuple[str, ...] = ("nomic-embed-text:latest",)
DEFAULT_EMBEDDING_BENCHMARK_CONCURRENCY: int = 4
DEFAULT_EMBEDDING_BENCHMARK_SAMPLE_COUNT: int = 15

# Embedding Benchmark Dry-Run Simulation Defaults
DEFAULT_DRY_RUN_EMBEDDING_DIMENSION: int = 768
DEFAULT_DRY_RUN_EMBEDDING_RECALL: float = 100.0
DEFAULT_DRY_RUN_EMBEDDING_MRR: float = 1.0
DEFAULT_DRY_RUN_EMBEDDING_NDCG: float = 1.0
DEFAULT_DRY_RUN_EMBEDDING_MARGIN: float = 0.45
DEFAULT_DRY_RUN_EMBEDDING_SEPARATION: float = 0.48
DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P50: float = 12.5
DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P95: float = 18.2
DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_ITEMS: float = 85.0
DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_CHARS: float = 18500.0
DEFAULT_DRY_RUN_EMBEDDING_OVERALL_SCORE: float = 95.0
DEFAULT_DRY_RUN_EMBEDDING_CATEGORIES: tuple[str, ...] = (
    "security",
    "kubernetes",
    "architecture",
    "ci_cd",
    "infrastructure",
)

# ── TLS & Cryptographic Defaults ──────────────────────────────────────────────
DEFAULT_TLS_DIR = CONST_CONFIG_DIR / CONST_TLS_DIR_NAME
DEFAULT_CA_VALIDITY_DAYS: int = 3650  # 10 years for Root CA
DEFAULT_TLS_VALIDITY_DAYS: int = 365  # 1 year for Server/Client Certs
DEFAULT_TLS_KEY_SIZE: int = 2048
DEFAULT_TLS_ORGANIZATION: str = "Homelab DevOps"
DEFAULT_TLS_COUNTRY: str = "US"
DEFAULT_HOMELAB_DOMAINS: tuple[str, ...] = (
    "*.homelab.local",
    "homelab.local",
    "*.local",
    "localhost",
    "argocd.homelab.local",
    "grafana.homelab.local",
    "prometheus.homelab.local",
    "ollama.homelab.local",
    "open-webui.homelab.local",
    "qdrant.homelab.local",
    "jaeger.homelab.local",
    "otel.homelab.local",
)
DEFAULT_HOMELAB_IPS: tuple[str, ...] = (
    "127.0.0.1",
    "::1",
    "192.168.49.2",  # Minikube standard node IP
)

# ── RAG & Vector Store Defaults ───────────────────────────────────────────────
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_RAG_COLLECTION = "devops_code"
DEFAULT_RAG_DOCS_COLLECTION = "devops_docs"
DEFAULT_RAG_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
DEFAULT_RAG_EMBEDDING_URL: str | None = None
DEFAULT_RAG_TOP_K: int = 5
DEFAULT_RAG_SCORE_THRESHOLD: float = 0.35
DEFAULT_RAG_CHUNK_SIZE: int = 2400
DEFAULT_RAG_CHUNK_OVERLAP: int = 240
DEFAULT_RAG_CACHE_DIR = DEFAULT_RAG_DATA_DIR

# ── Tracing & Telemetry Defaults ──────────────────────────────────────────────
DEFAULT_JAEGER_URL = "http://localhost:16686"
DEFAULT_OTEL_ENDPOINT = "http://localhost:4318"

# ── Tool & Agent Defaults ─────────────────────────────────────────────────────
DEFAULT_TOOL_READ_MAX_BYTES: int = 4000
DEFAULT_TOOL_MAX_BYTES_LIMIT: int = 5_000_000
DEFAULT_TOOL_DIFF_MAX_CHARS: int = 4000
DEFAULT_TOOL_MAX_FILES: int = 100
DEFAULT_TOOL_MAX_SEARCH_MATCHES: int = 50
DEFAULT_TOOL_BUFFER_CHUNK_SIZE: int = 65536
DEFAULT_AGENT_MAX_TURNS: int = 10
DEFAULT_MCP_SERVER_PORT: int = 8000
DEFAULT_MCP_TRANSPORT = "stdio"
DEFAULT_MCP_HOST = "127.0.0.1"

# ── Security Scanner & Scan Command Defaults ──────────────────────────────────
DEFAULT_TRIVY_SEVERITIES = "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL"
DEFAULT_TRIVY_SCAN_TYPE = "fs"
DEFAULT_TRIVY_TIMEOUT_SECONDS: float = 120.0
DEFAULT_KUBELINTER_TIMEOUT_SECONDS: float = 60.0
DEFAULT_POPEYE_TIMEOUT_SECONDS: float = 60.0
DEFAULT_PLUTO_TIMEOUT_SECONDS: float = 60.0
DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS: float = 10.0

# ── Telemetry HTTP Defaults ───────────────────────────────────────────────────
DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS: float = 1.0

# ── FastMCP Server Tool Execution Timeouts ─────────────────────────────────────
DEFAULT_MCP_TOOL_TIMEOUT_SECONDS: float = 300.0
DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS: float = 60.0
DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS: float = 30.0

# ── Docker Defaults ───────────────────────────────────────────────────────────
DEFAULT_DOCKER_TIMEOUT_SECONDS: float = 300.0

# ── Connection & Response Timeout Policies ───────────────────────────────────
# NOTE (Design Justification): Connection timeouts are intentionally short (1.0s)
# to fail fast when endpoints are unreachable, while response/read timeouts remain
# high (up to 3600s) to accommodate homelab performance and local AI/LLM inference.
DEFAULT_CONNECT_TIMEOUT_SECONDS: float = 1.0
DEFAULT_POOL_TIMEOUT_SECONDS: float = 1.0
DEFAULT_REVIEW_TIMEOUT_SECONDS: float = 1200.0
DEFAULT_REVIEW_WINDOW_SIZE_FACTOR: float = 0.8
DEFAULT_REVIEW_OVERLAP_FACTOR: float = 0.1
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes (kubectl, helm, minikube, git, gh)
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 3600.0  # 1 hour (API requests & downloads)
DEFAULT_DNS_TIMEOUT_SECONDS: float = 15.0  # 15 seconds (socket DNS resolution)

# ── Server & OpenAPI Defaults ──────────────────────────────────────────────────
DEFAULT_SERVER_TITLE: str = "DevOps CLI REST & OpenAPI Service"
DEFAULT_SERVER_DESCRIPTION: str = (
    "Asynchronous REST API and OpenAPI service engine for workstation automation, "
    "Kubernetes management, AI code reviews, and distributed telemetry."
)
DEFAULT_SERVER_DOCS_URL: str = "/docs"
DEFAULT_SERVER_REDOC_URL: str = "/redoc"
DEFAULT_SERVER_OPENAPI_URL: str = "/openapi.json"
DEFAULT_SERVER_HOST: str = "127.0.0.1"
DEFAULT_SERVER_PORT: int = 8000
DEFAULT_SERVER_WORKERS: int = 1
DEFAULT_LOG_LEVEL: str = "info"

# ── Output, Formatting & File Writing Defaults ─────────────────────────────────
DEFAULT_FORMAT_TYPE: str = "json"
DEFAULT_FILE_ENCODING: str = "utf-8"
DEFAULT_JSON_INDENT: int = 2
DEFAULT_SYNTAX_LANGUAGE: str = "text"
DEFAULT_SYNTAX_THEME: str = "monokai"
DEFAULT_PANEL_BORDER_STYLE: str = "cyan"
DEFAULT_TABLE_BORDER_STYLE: str = "dim"
DEFAULT_KEY_STYLE: str = "bold cyan"
DEFAULT_VALUE_STYLE: str = "green"
DEFAULT_PROGRESS_DESC_WORKING: str = "Working..."
DEFAULT_PROGRESS_DESC_PROCESSING: str = "Processing..."
DEFAULT_PROGRESS_TOTAL: float = 100.0
DEFAULT_BADGE_OK_COLOR: str = "green"
DEFAULT_BADGE_FAIL_COLOR: str = "red"
DEFAULT_BADGE_WARN_COLOR: str = "yellow"
DEFAULT_CODE_SPAN_COLOR: str = "cyan"
DEFAULT_STREAM_NAME: str = "stdout"

# ── AI, RAG & Agent Defaults ──────────────────────────────────────────────────
DEFAULT_TIKTOKEN_MODEL: str = "gpt-4o"
DEFAULT_TRUNCATION_SUFFIX: str = "\n...[truncated due to context budget]"
DEFAULT_DOC_CHUNK_SIZE_WORDS: int = 400
DEFAULT_DOC_CHUNK_OVERLAP_WORDS: int = 40
DEFAULT_DOC_MIN_CHUNK_WORDS: int = 80
DEFAULT_DOC_SAMPLE_COUNT: int = 15
DEFAULT_BENCHMARK_RANDOM_SEED: int = 42
DEFAULT_RERANKER_VECTOR_WEIGHT: float = 0.5
DEFAULT_RERANKER_LEXICAL_WEIGHT: float = 0.2
DEFAULT_RERANKER_BONUS: float = 0.15
DEFAULT_RERANKER_INTENT_BOOST: float = 0.1
DEFAULT_RAG_MAX_CHARS: int = 32000
DEFAULT_RAG_INVESTIGATION_MAX_CHARS: int = 24000
DEFAULT_RAG_MAX_PER_FILE: int = 8
DEFAULT_RAG_UPSERT_BATCH_SIZE: int = 64
DEFAULT_QDRANT_RETRY_ATTEMPTS: int = 3
DEFAULT_QDRANT_DISTANCE: str = "Cosine"
DEFAULT_AI_PROMPT_TEST: str = "Reply with exactly one word: OK"
DEFAULT_AI_PIPELINE_PROMPT: str = (
    "Perform a multi-agent review of workspace security, architecture, and code quality."
)
DEFAULT_AI_PIPELINE_PERSONAS: str = "devsecops,architect,qa"
DEFAULT_AI_PIPELINE_MAX_TURNS: int = 5
DEFAULT_AI_SYSTEM_PROMPT: str = "You are a helpful DevOps assistant."
DEFAULT_AI_AGENT_NAME: str = "Assistant"
DEFAULT_AI_PIPELINE_SESSION_ID: str = "pipeline-session"
DEFAULT_MOCK_LLM_RESPONSE: str = '{"findings": []}'
DEFAULT_AI_TIMEOUT_SECONDS: float = 60.0
DEFAULT_OPENAI_MODEL: str = "gpt-4o"
DEFAULT_OLLAMA_HOST: str = "http://localhost:11434"
DEFAULT_GITHUB_COPILOT_MODEL: str = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
DEFAULT_LLM_MAX_TOKENS: int = 8192
DEFAULT_AI_TEST_PROMPT: str = "Hello, world!"
DEFAULT_ESTIMATED_PROMPT_TOKENS: int = 1500

# ── Code Review, Scanner & Tooling Defaults ───────────────────────────────────
DEFAULT_BASE_BRANCH: str = "main"
DEFAULT_MATCH_ALL_PATTERN: str = "*"
DEFAULT_REVIEW_PERSONA: str = "devsecops"
DEFAULT_REVIEW_MAX_DIFF_CHARS: int = 128000
DEFAULT_LOCATION_CONTEXT_LINES: int = 12
DEFAULT_DIFF_CONTEXT_LINES: int = 12
DEFAULT_MAX_RELATED_FILES: int = 3
DEFAULT_RELATED_FILE_MAX_CHARS: int = 1500
DEFAULT_PRE_ANALYSIS_WORKERS: int = 4
DEFAULT_REVIEW_MAX_WORKERS: int = 4
DEFAULT_APPLY_PATCH_INDEX: int = 1
DEFAULT_INVALIDATED_STATUS: str = "INVALIDATED"
DEFAULT_BANDIT_SEVERITY: str = "medium"
DEFAULT_BANDIT_EXCLUDE: str = "B608"
DEFAULT_TRIVY_HIGH_SEVERITY: str = "HIGH,CRITICAL"
DEFAULT_KUBECONFORM_VERSION: str = "master"
DEFAULT_PACKAGE_ECOSYSTEM: str = "PyPI"
DEFAULT_CHECK_ALL: str = "all"
DEFAULT_AUDIT_STATUS_SUCCESS: str = "SUCCESS"
DEFAULT_SRC_DIR: str = "src"
DEFAULT_DOCS_FORMAT: str = "markdown"
DEFAULT_PYTEST_NUMPROCESSES: str = "auto"
DEFAULT_TABLE_FORMAT: str = "table"
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_EMBEDDING_BATCH_SIZE: int = 64
DEFAULT_RAG_MAX_CHUNKS_PER_FILE: int = 20
DEFAULT_RERANKER_DECLARATION_BONUS: float = 0.2
DEFAULT_RERANKER_SYMBOL_BONUS: float = 0.1
DEFAULT_FILE_FORMAT_AUTO: Literal["text", "bytes", "json", "yaml", "yml", "auto"] = "auto"
DEFAULT_CURRENT_PATH: Path = Path(".")

# ── Kubernetes, Port Forward & Homelab Defaults ───────────────────────────────
DEFAULT_K8S_DIR: Path = Path("k8s")
DEFAULT_K8S_NAMESPACE: str = "default"
DEFAULT_OBSERVABILITY_NAMESPACE: str = "observability"
DEFAULT_K8S_STACK: str = "infra"
DEFAULT_K8S_ALL_STACK: str = "all"
DEFAULT_K8S_TLS_SECRET_NAME: str = "homelab-tls"
DEFAULT_CERT_COMMON_NAME: str = "homelab.local"
DEFAULT_K8S_LOGS_TAIL: int = 100
DEFAULT_URL_REACHABILITY_TIMEOUT: float = 0.8
DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS: float = 0.8
DEFAULT_LOCAL_BIND_ADDRESS: str = "127.0.0.1"
DEFAULT_REST_HOST: str = "127.0.0.1"
DEFAULT_REST_PORT: int = 8000
DEFAULT_MCP_PORT: int = 8000
DEFAULT_ARGOCD_PORT: int = 8080
DEFAULT_GRAFANA_PORT: int = 8030
DEFAULT_GRAFANA_FOLDER_ID: int = 0
DEFAULT_PROMETHEUS_PORT: int = 8090
DEFAULT_JAEGER_PORT: int = 16686
DEFAULT_OTEL_PORT: int = 4318
DEFAULT_OLLAMA_PORT: int = 11434
DEFAULT_OPEN_WEBUI_PORT: int = 3000
DEFAULT_QDRANT_PORT: int = 6333
DEFAULT_VALKEY_PORT: int = 6379
DEFAULT_PROMETHEUS_QUERY_START: str = "1h"
DEFAULT_PROMETHEUS_QUERY_STEP: str = "60s"
DEFAULT_PROMETHEUS_QUERY_RANGE_START: str = "1h"
DEFAULT_PROMETHEUS_QUERY_RANGE_STEP: str = "60s"
DEFAULT_PROMETHEUS_DEFAULT_QUERY: str = "up"
DEFAULT_ARGOCD_DEFAULT_APP: str = "argocd"

# ── Release & Git Defaults ────────────────────────────────────────────────────
DEFAULT_RELEASE_TYPE: str = "feat"
DEFAULT_RELEASE_LABEL: str = "release"
DEFAULT_CLEAN_WORKSPACE_DAYS: int = 7
DEFAULT_GIT_LOG_COUNT: int = 10
DEFAULT_FIND_MAXDEPTH: int = 3
DEFAULT_PR_LIMIT: int = 30

# ── Telemetry Defaults ────────────────────────────────────────────────────────
DEFAULT_OTEL_COUNTER_AMOUNT: float = 1.0
DEFAULT_OTEL_TEST_TIMEOUT: float = 1.0
DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS: int = 50
DEFAULT_TELEMETRY_TEST_NAME: str = "devops-cli.manual_test"
