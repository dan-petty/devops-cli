"""Configuration defaults and consolidated high timeout values."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import (
    CONST_CONFIG_DIR,
    CONST_REVIEW_OVERLAP_FACTOR,
    CONST_REVIEW_TIMEOUT_SECONDS,
    CONST_REVIEW_WINDOW_SIZE_FACTOR,
    CONST_TLS_DIR_NAME,
    CONST_URL_OLLAMA_LOCALHOST,
)

# ── General Defaults ──────────────────────────────────────────────────────────
DEFAULT_LOCAL_BIN_DIR = Path.home() / ".local" / "bin"
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_WORKSPACE_FILE = Path(".code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "gemma4:26b"
DEFAULT_OLLAMA_URLS: tuple[str, ...] = (CONST_URL_OLLAMA_LOCALHOST,)
DEFAULT_OLLAMA_MAX_PARALLEL: int = 2
DEFAULT_AI_MAX_RETRIES: int = 2
DEFAULT_LLM_CACHE_ENABLED: bool = True
DEFAULT_LLM_CACHE_TTL_SECONDS: int = 86400 * 7  # 7 days
DEFAULT_LLM_CACHE_MAX_ENTRIES: int = 1000
DEFAULT_PYTHON_VERSION: str = "3.14"
DEFAULT_BUNDLE_MODELS: tuple[str, ...] = ("qwen2.5-coder:7b", "llama3.1:8b")
DEFAULT_PR_STATE = "open"
DEFAULT_MAX_CONTEXT_TOKENS: int = 16384
DEFAULT_DIFF_CHUNK_BUDGET: int = 8192
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
DEFAULT_RAG_TOP_K: int = 5
DEFAULT_RAG_SCORE_THRESHOLD: float = 0.35
DEFAULT_RAG_CHUNK_SIZE: int = 1000
DEFAULT_RAG_CHUNK_OVERLAP: int = 100
DEFAULT_RAG_CACHE_DIR = Path(".data/rag")

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
DEFAULT_REVIEW_TIMEOUT_SECONDS: float = float(CONST_REVIEW_TIMEOUT_SECONDS)  # 1200.0s
DEFAULT_REVIEW_WINDOW_SIZE_FACTOR: float = CONST_REVIEW_WINDOW_SIZE_FACTOR  # 0.8
DEFAULT_REVIEW_OVERLAP_FACTOR: float = CONST_REVIEW_OVERLAP_FACTOR  # 0.1
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes (kubectl, helm, minikube, git, gh)
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 3600.0  # 1 hour (API requests & downloads)
DEFAULT_DNS_TIMEOUT_SECONDS: float = 15.0  # 15 seconds (socket DNS resolution)

# ── Consolidated Aliases & Sub-keys ───────────────────────────────────────────
DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS

HTTP_CONNECT_TIMEOUT_SECONDS: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
HTTP_READ_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_WRITE_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_POOL_TIMEOUT_SECONDS: float = DEFAULT_POOL_TIMEOUT_SECONDS

DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_HTTP_LONG_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_HTTP_DOWNLOAD_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_GH_AUTH_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
DEFAULT_KEYRING_TIMEOUT_SECONDS: float = DEFAULT_HTTP_TIMEOUT_SECONDS
