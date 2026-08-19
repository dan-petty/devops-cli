"""Configuration defaults and consolidated high timeout values."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import (
    CONST_DEFAULT_AGENT_MAX_TURNS,
    CONST_DEFAULT_AI_MAX_RETRIES,
    CONST_DEFAULT_MCP_SERVER_PORT,
    CONST_DEFAULT_TOOL_BUFFER_CHUNK_SIZE,
    CONST_DEFAULT_TOOL_DIFF_MAX_CHARS,
    CONST_DEFAULT_TOOL_MAX_BYTES_LIMIT,
    CONST_DEFAULT_TOOL_MAX_FILES,
    CONST_DEFAULT_TOOL_MAX_SEARCH_MATCHES,
    CONST_DEFAULT_TOOL_READ_MAX_BYTES,
    CONST_REVIEW_OVERLAP_FACTOR,
    CONST_REVIEW_TIMEOUT_SECONDS,
    CONST_REVIEW_WINDOW_SIZE_FACTOR,
    CONST_URL_OLLAMA_LOCALHOST,
)
from devops_cli.config.metadata import get_project_python_version

# ── General Defaults ──────────────────────────────────────────────────────────
DEFAULT_SSH_KEY_DIR = Path.home() / ".ssh"
DEFAULT_SSH_ROTATION_DAYS = 90
DEFAULT_REPOS_BASE_DIR = Path("repos")
DEFAULT_WORKSPACE_FILE = Path(".code-workspace")
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_MODEL = "gemma4:26b"
DEFAULT_OLLAMA_URLS: tuple[str, ...] = (CONST_URL_OLLAMA_LOCALHOST,)
DEFAULT_AI_MAX_RETRIES: int = CONST_DEFAULT_AI_MAX_RETRIES
DEFAULT_PYTHON_VERSION = get_project_python_version()
DEFAULT_BUNDLE_MODELS: tuple[str, ...] = ("qwen2.5-coder:7b", "llama3.1:8b")

# ── RAG & Vector Store Defaults ───────────────────────────────────────────────
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_RAG_COLLECTION = "devops_code"
DEFAULT_RAG_DOCS_COLLECTION = "devops_docs"
DEFAULT_RAG_EMBEDDING_MODEL = "all-minilm"
DEFAULT_RAG_TOP_K: int = 5
DEFAULT_RAG_SCORE_THRESHOLD: float = 0.35
DEFAULT_RAG_CHUNK_SIZE: int = 500
DEFAULT_RAG_CHUNK_OVERLAP: int = 50
DEFAULT_RAG_CACHE_DIR = Path(".data/rag")

# ── Tracing & Telemetry Defaults ──────────────────────────────────────────────
DEFAULT_JAEGER_URL = "http://localhost:16686"
DEFAULT_OTEL_ENDPOINT = "http://localhost:4318"

# ── Tool & Agent Defaults ─────────────────────────────────────────────────────
DEFAULT_TOOL_READ_MAX_BYTES: int = CONST_DEFAULT_TOOL_READ_MAX_BYTES
DEFAULT_TOOL_MAX_BYTES_LIMIT: int = CONST_DEFAULT_TOOL_MAX_BYTES_LIMIT
DEFAULT_TOOL_DIFF_MAX_CHARS: int = CONST_DEFAULT_TOOL_DIFF_MAX_CHARS
DEFAULT_TOOL_MAX_FILES: int = CONST_DEFAULT_TOOL_MAX_FILES
DEFAULT_TOOL_MAX_SEARCH_MATCHES: int = CONST_DEFAULT_TOOL_MAX_SEARCH_MATCHES
DEFAULT_TOOL_BUFFER_CHUNK_SIZE: int = CONST_DEFAULT_TOOL_BUFFER_CHUNK_SIZE
DEFAULT_AGENT_MAX_TURNS: int = CONST_DEFAULT_AGENT_MAX_TURNS
DEFAULT_MCP_SERVER_PORT: int = CONST_DEFAULT_MCP_SERVER_PORT

# ── Security Scanner & Scan Command Defaults ──────────────────────────────────
DEFAULT_TRIVY_SEVERITIES = "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL"
DEFAULT_TRIVY_SCAN_TYPE = "fs"
DEFAULT_TRIVY_TIMEOUT_SECONDS: float = 120.0
DEFAULT_KUBELINTER_TIMEOUT_SECONDS: float = 60.0
DEFAULT_POPEYE_TIMEOUT_SECONDS: float = 60.0
DEFAULT_PLUTO_TIMEOUT_SECONDS: float = 60.0

# ── FastMCP Server Tool Execution Timeouts ─────────────────────────────────────
DEFAULT_MCP_TOOL_TIMEOUT_SECONDS: float = 300.0
DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS: float = 60.0
DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS: float = 30.0

# ── Docker Defaults ───────────────────────────────────────────────────────────
DEFAULT_DOCKER_TIMEOUT_SECONDS: float = 300.0

# ── High Timeout Policies ─────────────────────────────────────────────────────
# NOTE (Design Justification - AGENTS.md §4 & README.md): High default timeouts are intentional
# to accommodate local LLM inference (CPU/GPU Ollama), corporate proxy delays, and minikube setup.
DEFAULT_REVIEW_TIMEOUT_SECONDS: float = float(CONST_REVIEW_TIMEOUT_SECONDS)  # 1200.0s
DEFAULT_REVIEW_WINDOW_SIZE_FACTOR: float = CONST_REVIEW_WINDOW_SIZE_FACTOR  # 0.8
DEFAULT_REVIEW_OVERLAP_FACTOR: float = CONST_REVIEW_OVERLAP_FACTOR  # 0.1
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
