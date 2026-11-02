"""Configuration defaults and consolidated high timeout values."""

from __future__ import annotations

import ipaddress
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from typing import Final, Literal

from devops_cli.config.constants import (
    CONST_ANALYSIS_DIR_NAME,
    CONST_AUDIT_LOG_NAME,
    CONST_BENCHMARKS_DIR_NAME,
    CONST_CACHE_DIR_NAME,
    CONST_CONFIG_DIR,
    CONST_DOCS_DIR_PATH,
    CONST_FEEDBACK_DATASET_NAME,
    CONST_LOGS_DIR_NAME,
    CONST_MODELS_DIR_NAME,
    CONST_RAG_DIR_NAME,
    CONST_REVIEWS_DIR_NAME,
    CONST_RUNS_DIR_NAME,
    CONST_SAMPLES_DIR_NAME,
    CONST_TLS_DIR_NAME,
)

# ── Data Directories & Artifact Default Paths ─────────────────────────────────
DEFAULT_DATA_DIR = Path(".data")
DEFAULT_ANALYSIS_DATA_DIR = DEFAULT_DATA_DIR / CONST_ANALYSIS_DIR_NAME
DEFAULT_MAX_CACHED_ANALYSES: int = 15
DEFAULT_REVIEWS_DATA_DIR = DEFAULT_DATA_DIR / CONST_REVIEWS_DIR_NAME
DEFAULT_LOGS_DATA_DIR = DEFAULT_DATA_DIR / CONST_LOGS_DIR_NAME
DEFAULT_MODELS_DATA_DIR = DEFAULT_DATA_DIR / CONST_MODELS_DIR_NAME
DEFAULT_CACHE_DATA_DIR = DEFAULT_DATA_DIR / CONST_CACHE_DIR_NAME
DEFAULT_BENCHMARKS_DATA_DIR = DEFAULT_DATA_DIR / CONST_BENCHMARKS_DIR_NAME
DEFAULT_AUDIT_LOG_PATH = DEFAULT_LOGS_DATA_DIR / CONST_AUDIT_LOG_NAME
DEFAULT_FEEDBACK_DATASET_PATH = DEFAULT_DATA_DIR / CONST_FEEDBACK_DATASET_NAME
DEFAULT_TLS_DATA_DIR = DEFAULT_DATA_DIR / CONST_TLS_DIR_NAME
DEFAULT_RAG_DATA_DIR = DEFAULT_DATA_DIR / CONST_RAG_DIR_NAME
DEFAULT_SAMPLES_DATA_DIR = DEFAULT_DATA_DIR / CONST_SAMPLES_DIR_NAME
DEFAULT_RUNS_DATA_DIR = DEFAULT_DATA_DIR / CONST_RUNS_DIR_NAME
DEFAULT_SANDBOX_DATA_DIR = DEFAULT_DATA_DIR / "sandbox"
DEFAULT_SANDBOX_INSTANCES_FILE = DEFAULT_SANDBOX_DATA_DIR / "instances.json"
DEFAULT_SANDBOX_INCIDENTS_DIR = DEFAULT_SANDBOX_DATA_DIR / "incidents"
DEFAULT_SANDBOX_EXCLUDE_HOME: bool = True
DEFAULT_SANDBOX_NAMESPACE: str = "sandbox"

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
# A model that the gateway config sends to the tier of the default Ollama Service, and a gateway
# group of the same name, so `provider: ollama` and `provider: gateway` both find it. It is the
# model of the devops-chat route and of config.example.yaml. tests/test_k8s_llm_gateway.py binds
# it to k8s/llm/gateway/config.yaml.
DEFAULT_AI_MODEL = "qwen3.8:27b"
DEFAULT_AI_FALLBACK_PROVIDER = "ollama"
# A model that the gateway config sends to the tier of the default Ollama Service, the model of
# the devops-coder route. tests/test_k8s_llm_gateway.py binds it to k8s/llm/gateway/config.yaml.
DEFAULT_AI_FALLBACK_MODEL = "qwen3-coder:30b"
# The hosted model that local chat tokens are priced against: the owner's choice (#2194). The AI
# spend dashboard holds genai-prices' price of this model, and of the embedding reference below,
# and tests/test_k8s_monitoring_dashboards.py fails when the two differ.
DEFAULT_AI_REFERENCE_MODEL: str = "gpt-4o"
# The hosted model that local embedding tokens are priced against, and the genai-prices provider
# that prices both reference models: genai-prices finds no provider for an embedding model by its
# name alone (#1623).
DEFAULT_AI_REFERENCE_EMBEDDING_MODEL: str = "text-embedding-3-small"
DEFAULT_AI_REFERENCE_PROVIDER: str = "openai"
DEFAULT_AI_HARDWARE_COST_USD: float = 0.0
DEFAULT_AI_REASONING_EFFORT: str | None = None
DEFAULT_AI_SUPPORTS_REASONING: Final[bool] = False
DEFAULT_THINKING_MAX_THOUGHT_CHARS: Final[int] = 65_536
DEFAULT_THINKING_INITIAL_STATE: Final[str] = "emitting"
DEFAULT_THINKING_TAGS: Final[tuple[str, str]] = ("<think>", "</think>")
DEFAULT_AI_TEMPERATURE: float = 0.1
DEFAULT_AI_TOP_P: float = 0.95
DEFAULT_AI_CONTEXT_WINDOW: int = 32768
# The gateway group that serves one step of `devops roadmap implement` (#2664): qwen3-coder on a
# tier whose context length is 128000 tokens. A step builds its inputs to fit this window.
DEFAULT_AI_IMPLEMENT_MODEL: str = "devops-coder"
DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW: int = 128000
DEFAULT_OLLAMA_MAX_PARALLEL: int = 2
DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS: float = 900.0
DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS: float = 2.0
DEFAULT_AI_MAX_RESPONSE_BYTES: int = 50 * 1024 * 1024  # 50 MiB limit
# The most one streamed event, or one unterminated stream line, may hold before the stream is
# refused: httpx2's DEFAULT_MAX_EVENT_SIZE_BYTES. MAX_STREAM_BYTES still bounds the whole stream.
DEFAULT_AI_STREAM_MAX_EVENT_BYTES: int = 1024 * 1024
DEFAULT_AI_PREWARM_KEEP_ALIVE: str = "1h"
DEFAULT_AI_EVICT_KEEP_ALIVE: int = 0
DEFAULT_AI_MAX_RETRIES: int = 4
DEFAULT_AI_GATEWAY_PROVIDER: str = "litellm"
DEFAULT_AI_GATEWAY_URL: str = "http://localhost:4000/v1"
DEFAULT_PORTKEY_GATEWAY_URL: str = "http://localhost:8787/v1"
# The default Ollama Service (k8s/llm/profiles/services.yaml): the fast tier's speed Service. It
# names no VRAM size, so a host change moves its selector and not this name (#1637).
DEFAULT_OLLAMA_CLUSTER_SERVICE: str = "ollama-fast"
DEFAULT_OLLAMA_CLUSTER_URL: str = (
    f"http://{DEFAULT_OLLAMA_CLUSTER_SERVICE}.llm.svc.cluster.local:11434"
)
DEFAULT_AI_GATEWAY_ENABLED: bool = False
DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS: float = 5.0
# `devops ai gateway tune`: the sweep runs in an ephemeral container attached to the gateway pod,
# since the inference backends admit traffic only from the gateway. The image tracks this
# project's Python.
DEFAULT_AI_GATEWAY_SERVICE: str = "llm-gateway"
DEFAULT_AI_GATEWAY_DEPLOYMENT: str = "llm-gateway"
DEFAULT_GATEWAY_TUNE_IMAGE: str = "python:3.14-slim"
DEFAULT_GATEWAY_TUNE_MODEL_GROUP: str = "devops-review"
DEFAULT_GATEWAY_TUNE_CONCURRENCY: str = "1,4,8"
DEFAULT_GATEWAY_TUNE_ROUNDS: int = 2
DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS: int = 512
# `devops ai gateway load` looks back this far unless told otherwise.
DEFAULT_POOL_LOAD_WINDOW = "1h"
# Reply length for the capacity pass, and the cap on natural replies in the cost pass.
DEFAULT_GATEWAY_TUNE_MAX_TOKENS: int = 200
DEFAULT_GATEWAY_TUNE_REQUEST_TIMEOUT_SECONDS: float = 300.0
DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES: int = 2
DEFAULT_STRUCTURED_RETRY_BACKOFF_SECONDS: float = 0.5
DEFAULT_LLM_CACHE_ENABLED: bool = True
DEFAULT_LLM_CACHE_TTL_SECONDS: int = 86400 * 7  # 7 days
DEFAULT_LLM_CACHE_MAX_ENTRIES: int = 1000
DEFAULT_PYTHON_VERSION: str = "3.14"
DEFAULT_PR_STATE = "open"
DEFAULT_MAX_CONTEXT_TOKENS: int = 32768
DEFAULT_DIFF_CHUNK_BUDGET: int = 32768
DEFAULT_SEMGREP_CONFIG: str = "p/default"

# ── Benchmark Defaults ────────────────────────────────────────────────────────
DEFAULT_BENCHMARK_CONCURRENCY: int = 4
DEFAULT_BENCHMARK_FORMAT: str = "table"
DEFAULT_BENCHMARK_SAMPLES: int = 5
DEFAULT_BENCHMARK_TYPE: str = "auto"
DEFAULT_EMBEDDING_BENCHMARK_MODELS: tuple[str, ...] = ("bge-m3:latest", "qwen3-embedding:0.6b")
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
    "tempo.homelab.local",
    "otel.homelab.local",
)
DEFAULT_HOMELAB_IPS: tuple[IPv4Address | IPv6Address, ...] = (
    ipaddress.ip_address("127.0.0.1"),
    ipaddress.ip_address("::1"),
    ipaddress.ip_address("192.168.49.2"),  # Minikube standard node IP
)

# ── RAG & Vector Store Defaults ───────────────────────────────────────────────
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_RAG_COLLECTION = "devops_code"
DEFAULT_RAG_DOCS_COLLECTION = "devops_docs"
DEFAULT_RAG_LIBRARIES_COLLECTION = "devops_libraries"
DEFAULT_VALKEY_SYMBOL_TTL_SECONDS = 604800  # 7 days TTL for cached symbol signatures
DEFAULT_RAG_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
# The models of `devops ai bundle-models`: the models that the default chat and embedding tasks
# call, so an air-gapped devcontainer holds the models that the defaults name.
DEFAULT_BUNDLE_MODELS: tuple[str, ...] = (DEFAULT_AI_MODEL, DEFAULT_RAG_EMBEDDING_MODEL)
DEFAULT_RAG_EMBEDDING_CACHE_SIZE: int = 1024  # Max entries in in-memory embedding LRU cache
DEFAULT_RAG_EMBEDDING_TIMEOUT: float = 15.0  # Read timeout of one direct Ollama node, then failover
# Read timeout of one embedding batch sent to the gateway or to an OpenAI-compatible API. On
# 2026-10-23, the slowest batch that a gateway tier answered took 76 s, and a 30 s read timeout
# stopped 70 batches at 29 to 30 s. 120 s is more than 1.5 times the slowest reply (#2011).
DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT: float = 120.0
DEFAULT_RAG_EMBEDDING_BATCH_SIZE: int = 32  # Dynamic batch starting size
DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE: int = 1  # Smallest batch: one text, whose failure raises
DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS: float = 2.0  # Target latency ceiling
# A batch counts toward an increase of the batch size only when it takes at most this share of
# the latency threshold. One increase step adds 2 texts (CONST_AIMD_ADDITIVE_INCREASE_STEP), so
# for a size of 2 texts or more, the new size is not more than two times the old size. When the
# latency of a batch increases at most linearly with its size, a size whose batch takes half of
# the threshold or less can become two times as large and stay at or below the threshold.
DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO: float = 0.5
# After each change of the batch size, a fast batch counts toward an increase only after this
# time. A direct Ollama node gives its reply or its read timeout for a request in the default
# read timeout of a node (DEFAULT_RAG_EMBEDDING_TIMEOUT) or less. Thus no request that was sent
# before the change counts toward the next increase.
DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS: float = DEFAULT_RAG_EMBEDDING_TIMEOUT
DEFAULT_RAG_EMBEDDING_BACKOFF_BASE_SECONDS: float = 0.5  # Base delay for exponential backoff
DEFAULT_RAG_EMBEDDING_MAX_BACKOFF_SECONDS: float = 2.0  # Max delay cap for backoff
DEFAULT_VALKEY_EMBEDDING_TTL_SECONDS: int = 604800  # 7 days TTL for cached chunk embeddings
DEFAULT_RAG_TOP_K: int = 5
DEFAULT_RAG_SCORE_THRESHOLD: float = 0.35
DEFAULT_RAG_CHUNK_SIZE: int = 2400
DEFAULT_RAG_CHUNK_OVERLAP: int = 240
DEFAULT_RAG_CACHE_DIR = DEFAULT_RAG_DATA_DIR

# ── Tracing & Telemetry Defaults ──────────────────────────────────────────────
DEFAULT_TEMPO_URL = "http://localhost:3200"
DEFAULT_OTEL_ENDPOINT = "http://localhost:4318"
DEFAULT_LOKI_URL = "http://localhost:3100"
DEFAULT_PYROSCOPE_URL = "http://localhost:4040"

# ── Tool & Agent Defaults ─────────────────────────────────────────────────────
DEFAULT_TOOL_READ_MAX_BYTES: int = 4000
DEFAULT_TOOL_MAX_BYTES_LIMIT: int = 50 * 1024 * 1024  # 50 MiB limit
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
DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS: float = 10.0
DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS: float = 300.0
# The most files one Semgrep run of a review names; each batch has its own timeout, so one that
# runs out of time loses only its files (#1079). Offline with the cached p/default, one run of 300
# files took 81 to 93 s and three batches of 100 took 88 to 94 s in all (#1144): 100 files take
# about 30 s, a tenth of the timeout.
DEFAULT_SEMGREP_REVIEW_BATCH_FILES: int = 100
# The most bytes a registry ruleset download may hold; p/default is 2.5 MB.
DEFAULT_SEMGREP_REGISTRY_MAX_BYTES: int = 32 * 1024 * 1024
DEFAULT_SEMGREP_REGISTRY_TIMEOUT_SECONDS: float = 60.0
# A cached registry ruleset older than this is still used, with a warning that names its age.
DEFAULT_SEMGREP_REGISTRY_TTL_SECONDS: int = 86_400


# ── Telemetry HTTP Defaults ───────────────────────────────────────────────────
DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS: float = 1.0

# ── FastMCP Server Tool Execution Timeouts ─────────────────────────────────────
DEFAULT_MCP_TOOL_TIMEOUT_SECONDS: float = 300.0
DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS: float = 60.0
DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MCP_SCHEMA_CACHE_MAX_ENTRIES: int = 256

# ── Docker Defaults ───────────────────────────────────────────────────────────
DEFAULT_DOCKER_TIMEOUT_SECONDS: float = 300.0
DEFAULT_COSIGN_TIMEOUT_SECONDS: float = 60.0

# ── Vault Lease Lifecycle Defaults ───────────────────────────────────────────
# Renew a lease once its remaining lifetime drops below this fraction of its TTL, so a
# long CI run never presents an expired credential mid-operation.
DEFAULT_VAULT_LEASE_RENEW_THRESHOLD: float = 0.25
# Lifetime requested on each renewal, in seconds.
DEFAULT_VAULT_LEASE_RENEW_INCREMENT_SECONDS: int = 3600
# Bound on a single Vault HTTP API call.
DEFAULT_VAULT_REQUEST_TIMEOUT_SECONDS: float = 10.0

# ── Argo GitOps & Progressive Delivery Defaults ──────────────────────────────
# (DEFAULT_ARGOCD_NAMESPACE is defined with the Kubernetes namespace defaults below.)
# Refresh cadence for the live `devops argo rollouts status --watch` view.
DEFAULT_ROLLOUT_WATCH_INTERVAL_SECONDS: float = 2.0
# Poll cadence and wall-clock budget for `devops argo workflows submit --wait`.
DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS: float = 3.0
DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS: float = 1800.0

# Engine API socket handshake budget. Short by design: the daemon socket is local,
# so a slow ping means the daemon is down rather than merely busy.
DEFAULT_DOCKER_PING_TIMEOUT_SECONDS: float = 2.0
# Reachability and introspection response cache lifetime, mirroring the Kubernetes
# service cache tier so repeated command invocations avoid redundant round-trips.
DEFAULT_DOCKER_CACHE_TTL_SECONDS: float = 5.0
# Lifetime of a remembered failed Engine API answer. Short by design, so a daemon that comes
# back is noticed at the next command rather than after the full cache lifetime.
DEFAULT_DOCKER_FAILURE_CACHE_TTL_SECONDS: float = 2.0
# Grace period granted to a container to flush and exit before SIGKILL.
DEFAULT_DOCKER_STOP_TIMEOUT_SECONDS: int = 10
# ── Connection & Response Timeout Policies ───────────────────────────────────
# NOTE (Design Justification): Connection timeouts are intentionally short (1.0s)
# to fail fast when endpoints are unreachable, while response/read timeouts remain
# high (up to 3600s) to accommodate homelab performance and local AI/LLM inference.
DEFAULT_CONNECT_TIMEOUT_SECONDS: float = 1.0
DEFAULT_AI_CONNECT_TIMEOUT_SECONDS: float = 5.0
# The GitHub session's connect timeout (#983): api.github.com is reached over the public
# internet, where Linux resends a lost SYN after 1, 2 and 4 s and a TLS handshake on a lossy link
# runs longer, so the 1 s bound meant for local services failed live reads. It stays well under
# the 30 s gh's own dialer allows.
DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_POOL_TIMEOUT_SECONDS: float = 1.0
DEFAULT_REVIEW_TIMEOUT_SECONDS: float = 1200.0
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes (kubectl, helm, minikube, git, gh)
# `devops ci mutate`'s `mutmut run`. The first run mutates the whole source tree (about 196,000
# mutants, 506 s with 8 processes at a load average of 25) and then runs the test suite once,
# serially, for its stats.
DEFAULT_CI_MUTATE_TIMEOUT_SECONDS: float = 14400.0  # 4 hours
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 3600.0  # 1 hour (API requests & downloads)
DEFAULT_HTTP_MAX_REDIRECTS: int = 10  # hops the HTTP broker follows; httpx2 allows 20
DEFAULT_DNS_TIMEOUT_SECONDS: float = 15.0  # 15 seconds (socket DNS resolution)
DEFAULT_STACK_AUTH_TIMEOUT_SECONDS: float = 5.0  # 5 seconds bounded timeout for stack token minting

# ── Server & OpenAPI Defaults ──────────────────────────────────────────────────
DEFAULT_SERVER_TITLE: str = "DevOps CLI REST & OpenAPI Service"
DEFAULT_SERVER_DESCRIPTION: str = (
    "Asynchronous REST API and OpenAPI service engine for workstation automation, "
    "Kubernetes management, AI code reviews, and distributed telemetry."
)
DEFAULT_SERVER_DOCS_URL: str = "/docs"
DEFAULT_SERVER_REDOC_URL: str = "/redoc"
DEFAULT_SERVER_OPENAPI_URL: str = "/openapi.json"
DEFAULT_SERVER_WORKERS: int = 1
DEFAULT_LOG_LEVEL: Final = "info"

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
DEFAULT_STREAM_NAME: Final = "stdout"
DEFAULT_STREAM_PERSONA: str = "devsecops"
DEFAULT_ALLOWED_STREAM_PERSONAS: frozenset[str] = frozenset(
    {"devsecops", "architect", "challenger", "auditor", "qa", "pm"}
)

# ── AI, RAG & Agent Defaults ──────────────────────────────────────────────────
DEFAULT_TIKTOKEN_MODEL: str = "gpt-4o"
DEFAULT_TIKTOKEN_CACHE_ENV_VARS: tuple[str, ...] = ("TIKTOKEN_CACHE_DIR", "DATA_GYM_CACHE_DIR")
DEFAULT_TIKTOKEN_FALLBACK_CACHE_DIRS: tuple[str, ...] = (
    "/app/.cache/tiktoken",
    "/usr/local/share/tiktoken",
)
DEFAULT_TRUNCATION_SUFFIX: str = "\n...[truncated due to context budget]"
DEFAULT_RERANKER_VECTOR_WEIGHT: float = 0.5
DEFAULT_RERANKER_LEXICAL_WEIGHT: float = 0.2
DEFAULT_RERANKER_INTENT_BOOST: float = 0.1
DEFAULT_RAG_MAX_CHARS: int = 32000
DEFAULT_RAG_INVESTIGATION_MAX_CHARS: int = 24000
DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS: int = 2048  # Longer lookup queries are cut
DEFAULT_RAG_KB_SYNC_FAILURE_COOLDOWN_SECONDS: Final[float] = (
    1800.0  # 30-minute cooldown on KB rebuild failure
)
# `qdrant.timeout`: how long each Qdrant request, a search or an indexing upsert or delete, waits
# per attempt. 60 s is too short for a homelab Qdrant search; 300 to 600 s suits one (#975).
DEFAULT_QDRANT_TIMEOUT_SECONDS: float = 300.0
DEFAULT_QDRANT_DISTANCE: str = "Cosine"
DEFAULT_AI_PIPELINE_PROMPT: str = (
    "Perform a multi-agent review of workspace security, architecture, and code quality."
)
DEFAULT_AI_PIPELINE_PERSONAS: str = "devsecops,architect,qa"
DEFAULT_AI_PIPELINE_MAX_TURNS: int = 5
DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS: int = 4096
DEFAULT_AI_TEST_PROMPT: str = "Hello, world!"
DEFAULT_MAX_AST_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50MB DoS protection limit
DEFAULT_AI_SPEND_DB_FILENAME: str = "spend.db"
DEFAULT_AI_PRICING_OVERRIDES_FILENAME: str = "pricing_overrides.json"

DEFAULT_MATCH_ALL_PATTERN: str = "*"
DEFAULT_REVIEW_MAX_DIFF_CHARS: int = 128000
# Runs per review benchmark; findings vary between identical runs, so medians need several.
DEFAULT_REVIEW_BENCHMARK_RUNS: int = 3
# Seed for synthetic defect corpora; the same seed and files give the same injections.
DEFAULT_REVIEW_CORPUS_SEED: int = 1
DEFAULT_REVIEW_LINE_OVERLAP_TOLERANCE: int = 2
DEFAULT_REVIEW_TITLE_SIMILARITY_THRESHOLD: float = 0.5
DEFAULT_REVIEW_MAX_TITLE_LENGTH: int = 200
DEFAULT_REVIEW_MAX_SUMMARY_PREVIEW_LENGTH: int = 300
# Recurring defect classes a review's headline names; the Key Bad Patterns section lists them all.
DEFAULT_REVIEW_HEADLINE_THEMES: int = 3
DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_CRITERIA_MAX_OUTPUT_BYTES: Final[int] = 4096
DEFAULT_HOST_SANDBOX_BINARY: Final[str] = "/usr/bin/bwrap"
DEFAULT_PRE_ANALYSIS_WORKERS: int = 4
DEFAULT_REVIEW_CONCURRENCY: int = 4
DEFAULT_GATEWAY_REVIEW_SLOTS: dict[str, int] = {
    "http://ollama-48gib-fast.llm.svc.cluster.local:11434": 1,
    "http://ollama-64gib-standard.llm.svc.cluster.local:11434": 1,
    "http://ollama-16gib-fast.llm.svc.cluster.local:11434": 1,
}
DEFAULT_GATEWAY_REVIEW_CONCURRENCY: int = sum(DEFAULT_GATEWAY_REVIEW_SLOTS.values())
# The longest a gateway chat request waits for one of those slots, as long as an Ollama lease.
DEFAULT_GATEWAY_SLOT_TIMEOUT_SECONDS: float = 900.0
DEFAULT_REVIEW_MAX_CONCURRENCY: int = 32
DEFAULT_REVIEW_RATE_LIMIT: float = 10.0
DEFAULT_REVIEW_RATE_CAPACITY: float = 10.0
DEFAULT_BANDIT_SEVERITY: str = "medium"
# The niceness `devops ci security` starts Bandit with (#1725). The test row is the full gate's
# critical path, and Bandit beside its workers took 61 s against 21 s alone; niced, it takes the
# CPU they leave idle instead of theirs. 10 rather than 19: the scheduler weighs a niceness of 10
# at about a tenth of 0, and 19 at about a seventieth, so on a host other work keeps busy Bandit
# still finishes. On an idle CPU a niced process runs at full speed.
DEFAULT_CI_BANDIT_NICENESS: Final[int] = 10
# `devops ci test --repeat`: 0 is a single run in file order; ci.yml's pull-request job passes 3.
DEFAULT_CI_TEST_REPEAT_RUNS: Final[int] = 0
# The workers of a narrowed `devops ci test <paths>` run given no `-n` (#1669): serial up to this
# many test modules, then this many workers. The full suite keeps addopts' `-n logical`. Median of
# 3 runs at load 7-30 on 16 CPUs, wall and CPU seconds at -n 0 / 4 / 16: 1 module 6 / 11 / 15 s
# and 9 / 30 / 133 CPU-s; 8 modules 36 / 51 / 40 s and 37 / 101 / 303 CPU-s; 12 modules 79 / 82 /
# 54 s and 84 / 193 / 358 CPU-s, so serial matched 4 workers at less than half their CPU; 19
# modules 75 / 27 / 39 s and 75 / 89 / 357 CPU-s, so 4 workers ran 2.8 times faster than serial at
# about the same CPU. A source module selects a median of 3 test modules and a p90 of 12; 90%
# select at most 12.
DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12
DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4
# `devops ci job-time` (#2699): how many of the last runs of the test job its mean covers.
DEFAULT_CI_JOB_TIME_RUNS: Final[int] = 10
# `devops ci` gate slots (#2336): one slot for each this many CPUs, at least one. The full suite
# starts one pytest worker for each CPU, so a gate saturates a host alone. On 16 CPUs on
# 2026-10-27, 11189 tests took 247 s alone, inside the 300 s test budget, and two gates side by
# side took 440 s each and used 926 of the 2048 process ids of the container; two gates finished
# both jobs only 11% sooner than two in turn. So 16 CPUs give 1 slot, 32 give 2, and the 4-CPU
# GitHub runner gives 1, where a single job never waits.
DEFAULT_CI_GATE_CPUS_PER_SLOT: Final[int] = 16
# How long a gate that waits for a slot sleeps before it tries the slots again.
DEFAULT_CI_GATE_POLL_SECONDS: Final[float] = 2.0
# How long one `openspec` command may run before the gate stops it. Each ran in 0.3 to 1.5 s
# against the pinned 1.14.3 on 2026-10-22 (ADR 0010); the bound is a hang bound, since an earlier
# release of the tool hung `validate --all` under pre-commit.
DEFAULT_OPENSPEC_COMMAND_TIMEOUT_SECONDS: Final[float] = 120.0
DEFAULT_TRIVY_HIGH_SEVERITY: str = "HIGH,CRITICAL"
DEFAULT_KUBECONFORM_VERSION: str = "master"
DEFAULT_PACKAGE_ECOSYSTEM: str = "PyPI"
DEFAULT_SRC_DIR: str = "src"
DEFAULT_DOCS_FORMAT: str = "markdown"
DEFAULT_TABLE_FORMAT: str = "table"
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_EMBEDDING_BATCH_SIZE: int = 64
DEFAULT_RAG_MAX_CHUNKS_PER_FILE: int = 20
DEFAULT_RERANKER_DECLARATION_BONUS: float = 0.2
DEFAULT_RERANKER_SYMBOL_BONUS: float = 0.1
DEFAULT_FILE_FORMAT_AUTO: Literal["text", "bytes", "json", "yaml", "yml", "auto"] = "auto"
DEFAULT_CURRENT_PATH: Path = Path(".")
# The directory `devops scan workflows` audits: GitHub Actions workflows and composite actions.
DEFAULT_WORKFLOWS_SCAN_PATH: Path = Path(".github")

# ── Kubernetes, Port Forward & Homelab Defaults ───────────────────────────────
DEFAULT_K8S_DIR: Path = Path("k8s")
DEFAULT_K8S_NAMESPACE: str = "default"
DEFAULT_OBSERVABILITY_NAMESPACE: str = "observability"
DEFAULT_K8S_STACK: str = "infra"
DEFAULT_K8S_ALL_STACK: str = "all"
DEFAULT_K8S_TLS_SECRET_NAME: str = "homelab-tls"
DEFAULT_CERT_COMMON_NAME: str = "homelab.local"
DEFAULT_K8S_LOGS_TAIL: int = 100
DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS: float = 0.8
DEFAULT_REST_HOST: str = "127.0.0.1"
# The local port of `devops k8s tunnel`, which forwards the Kubernetes API route of the
# Cloudflare tunnel (k8s/README.md, "The Kubernetes API at k8s.<domain>").
DEFAULT_K8S_TUNNEL_PORT: int = 16443
DEFAULT_REST_PORT: int = 8000
DEFAULT_MCP_PORT: int = 8000
DEFAULT_ARGOCD_PORT: int = 8080
DEFAULT_GRAFANA_PORT: int = 8030
DEFAULT_GRAFANA_FOLDER_ID: int = 0
DEFAULT_PROMETHEUS_PORT: int = 8090
DEFAULT_TEMPO_PORT: int = 3200
DEFAULT_OTEL_PORT: int = 4318
DEFAULT_PYROSCOPE_PORT: int = 4040
DEFAULT_OLLAMA_PORT: int = 11434
DEFAULT_OPEN_WEBUI_PORT: int = 3000
DEFAULT_QDRANT_PORT: int = 6333
DEFAULT_VALKEY_PORT: int = 6379
DEFAULT_PROMETHEUS_QUERY_RANGE_START: str = "1h"
DEFAULT_PROMETHEUS_QUERY_RANGE_STEP: str = "60s"
# ── Git Defaults ──────────────────────────────────────────────────────────────
DEFAULT_CLEAN_WORKSPACE_DAYS: int = 7
DEFAULT_GIT_LOG_COUNT: int = 10
DEFAULT_FIND_MAXDEPTH: int = 3
DEFAULT_PR_LIMIT: int = 30

# ── Telemetry Defaults ────────────────────────────────────────────────────────
DEFAULT_OTEL_COUNTER_AMOUNT: float = 1.0
DEFAULT_OTEL_TEST_TIMEOUT: float = 1.0
DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS: int = 50
# Longest a command's exit waits for telemetry exports still in flight.
DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS: float = 1.0
# How often an interactive user is told, per endpoint, that telemetry exports fail.
DEFAULT_OTEL_WARNING_INTERVAL_SECONDS: int = 86400
DEFAULT_TELEMETRY_TEST_NAME: str = "devops-cli.manual_test"
# `telemetry profile` polls Tempo until a trace stops growing, for at most this long.
DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS: float = 10.0
DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS: float = 0.5
# Longest one weaver call may take in `telemetry semconv refresh`; packaging the GenAI
# registry, two git clones included, took about 9 s.
DEFAULT_SEMCONV_WEAVER_TIMEOUT_SECONDS: float = 300.0

# ── AI Context Packing & AST Defaults ────────────────────────────────────────
DEFAULT_CONTEXT_PACKING_MAX_TOKENS: int = 1500
DEFAULT_CONTEXT_PACKING_TOTAL_BUDGET: int = 3000
DEFAULT_REPOMAP_MAX_FILES: int = 100
DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MiB
DEFAULT_JSON_REPAIR_MAX_LENGTH: int = 50 * 1024 * 1024  # 50 MiB
DEFAULT_TOOL_EXTRACT_PAGE_SIZE: int = 32 * 1024  # 32 KiB
DEFAULT_TOOL_EXTRACT_OVERLAP: int = 1024  # 1 KiB

# ── AI Firecrawl Search Defaults ────────────────────────────────────────────────
DEFAULT_FIRECRAWL_SEARCH_URL: str = "https://api.firecrawl.dev/v2/search"
DEFAULT_FIRECRAWL_SEARCH_LIMIT: int = 5
DEFAULT_FIRECRAWL_TIMEOUT_SECONDS: float = 30.0

DEFAULT_SIGNATURE_BODY: str = "..."
DEFAULT_TOOL_INTERFACE_FORMAT: Literal["python", "markdown"] = "python"
DEFAULT_PROJECT_VERSION: str = "0.1.0"
DEFAULT_PYTHON_REQUIRES: str = ">=3.14"
# The checks a generated AGENTS.md names before a push when the project has no pre-push hook.
DEFAULT_AGENTS_MD_CHECK_COMMANDS: tuple[str, ...] = (
    "uv run pytest",
    "uv run ruff check",
    "uv run mypy src",
)

DEFAULT_FINDING_STATUS: str = "UNVERIFIED"
DEFAULT_SYNTHESIZED_TEST_STATUS: str = "UNEXECUTED"
DEFAULT_AGENT_NAME: str = "Assistant"
DEFAULT_AGENT_SYSTEM_PROMPT: str = "You are a helpful DevOps assistant."
DEFAULT_PLAN_REMINDER_CADENCE: int = 3
DEFAULT_PLAN_REMINDER_ID: str = "system_reminders"
DEFAULT_INVARIANT_REMINDER_ID: str = "invariants"
DEFAULT_INVARIANT_REMINDER_CHARS: int = 120
DEFAULT_CHAT_INVARIANTS: tuple[str, ...] = (
    "Never echo plaintext secrets, tokens, private keys, or the contents of hidden or .gitignored files.",
    "Never write concrete internal hostnames, private RFC 1918 addresses, private registries, or homelab topology into any artifact; examples use example.com, RFC 5737 blocks, or localhost.",
    "Never lower, relax, bypass, or disable a security standard, quality threshold, or compliance check unless explicitly instructed by the user.",
    "Never push with --no-verify or before the pre-push hook passes. Never commit or push directly to main.",
)
DEFAULT_EMBEDDING_MODEL_NAME: str = "default"
DEFAULT_EMBEDDING_PROVIDER_NAME: str = "devops-cli"
DEFAULT_EMBEDDING_MODEL: str = "openai:text-embedding-3-small"
DEFAULT_EMBEDDING_INPUT_TYPE: Literal["query", "document"] = "query"
DEFAULT_EMBEDDING_CURRENCY: str = "USD"

# ── Valkey Defaults ─────────────────────────────────────────────────────────
DEFAULT_VALKEY_URL: str = f"valkey://localhost:{DEFAULT_VALKEY_PORT}/0"
DEFAULT_VALKEY_TIMEOUT_SECONDS: float = 2.0
# The circuit breaker of the Valkey cache tier (`devops_cli.valkey.cache`, #2073). One failed
# command opens it: a failed command can cost the full `valkey.timeout`, and a miss costs only the
# work that the cache saves. For the cooldown the tier sends no command, and then one trial
# command decides. The caches of a process share one tier (#1992), so an outage costs one
# connection attempt in each 60 s for the whole process. The cooldown is pybreaker's own default
# `reset_timeout` and the pause of the RAG lookups.
DEFAULT_VALKEY_CACHE_BREAKER_FAILURES: int = 1
DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS: float = 60.0
# The cache tier waits at most this long for a connection, and at most `valkey.timeout` (#1992).
# A silent Valkey host then costs 0.25 s, not the 2.0 s of `valkey.timeout`. Measured on
# 2026-10-29: a loopback connect took at most 0.6 ms, and a connect to a Service on another node
# of the homelab took at most 0.4 ms, so the bound is more than 400 times the slowest connect.
DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS: float = 0.25
# Commands wait at most this long on the run index before keeping a run locally only.
DEFAULT_RUNS_INDEX_TIMEOUT_SECONDS: float = 2.0

# ── Sparse Lexical (BM25) Ranking Defaults ───────────────────────────────────
# Term-frequency saturation and length-normalisation constants. These are the values
# established by the Okapi BM25 literature and used unchanged across both consumers.
DEFAULT_BM25_K1: float = 1.5
DEFAULT_BM25_B: float = 0.75
# ── Qdrant Vector Quantization ───────────────────────────────────────────────
# Store vectors as int8 rather than float32. Trades a small amount of recall for roughly
# a quarter of the memory footprint, which keeps a large index viable on a workstation.
DEFAULT_QDRANT_QUANTIZATION_ENABLED: bool = True
# Quantile bounding the int8 range, discarding extreme outliers that would otherwise
# compress the scale for every other value.
DEFAULT_QDRANT_QUANTIZATION_QUANTILE: float = 0.99

# ── Client-Side Metric Analysis ──────────────────────────────────────────────
# Standard deviations from the mean before a sample is reported as anomalous.
DEFAULT_ANOMALY_Z_THRESHOLD: float = 3.0
# Minimum series length before anomaly detection runs. Below this a baseline cannot be
# established, and a reported "anomaly" would be noise dressed as signal.
DEFAULT_ANOMALY_MIN_SAMPLES: int = 8
# Exponential smoothing factor; higher values track level shifts faster.
DEFAULT_EWMA_ALPHA: float = 0.3
# Samples projected beyond the observed window.
DEFAULT_FORECAST_HORIZON_SAMPLES: int = 5

# ── Grafana Panel Layout ─────────────────────────────────────────────────────
# Default panel height in grid rows, and the single-row height Grafana uses for section
# separators.
DEFAULT_GRAFANA_PANEL_HEIGHT: int = 8
DEFAULT_GRAFANA_ROW_HEIGHT: int = 1

# ── Watcher Defaults ────────────────────────────────────────────────────────
DEFAULT_FILE_WATCHER_DEBOUNCE_MS: int = 500
DEFAULT_FILE_WATCHER_INTERVAL_SECONDS: float = 0.5
DEFAULT_FILE_WATCHER_NAME: str = "file_watcher"
DEFAULT_RESOURCE_WATCHER_INTERVAL_SECONDS: float = 2.0
DEFAULT_RESOURCE_WATCHER_NAME: str = "resource_watcher"

# ── Project, Security & SBOM Defaults ───────────────────────────────────────
DEFAULT_PROJECT_NAME: str = "devops-cli"
DEFAULT_DEPENDENCY_MIN_SEVERITY: str = "HIGH"
DEFAULT_MAX_COMPLEXITY: int = 10
DEFAULT_QUANTIZATION_BITS: int = 16

DEFAULT_SANDBOX_NAME: str = "app-sandbox"
DEFAULT_SANDBOX_IMAGE: str = "python:3.14-slim"
DEFAULT_SANDBOX_MEMORY: str = "2g"
DEFAULT_SANDBOX_CPUS: float = 2.0
DEFAULT_SANDBOX_PIDS_LIMIT: int = 256
DEFAULT_SANDBOX_NETWORK: str = "isolated"
# ── Kubernetes & Argo Defaults ──────────────────────────────────────────────
DEFAULT_CHAOS_DURATION_SECONDS: int = 30
DEFAULT_ARGOCD_NAMESPACE: str = "argocd"
DEFAULT_LLM_NAMESPACE: str = "llm"
DEFAULT_BOOTSTRAP_STACK: str = "infra"
DEFAULT_LOG_QUERY_LIMIT: int = 100
DEFAULT_LOG_QUERY_SINCE: str = "1h"
DEFAULT_LOG_TAIL_LINES: int = 100
DEFAULT_LOG_MAX_LINE_CHARS: int = 65536
DEFAULT_K8S_POLICY_ENGINE: str = "kyverno"
DEFAULT_ARGO_FLEET_NAME: str = "default-fleet"
DEFAULT_ARGO_FLEET_CONCURRENCY: int = 3
# `gh label list` stops at 30 unless asked for more; .github/labels.yml alone holds 31.
DEFAULT_GH_LABEL_LIST_LIMIT: int = 1000
DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS: int = 6
DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS: float = 5.0
DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS: float = 30.0
DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS: float = 120.0
# The wall-clock bound on one gh process walking every `Link` page of a `devops gh api
# --paginate` call (#983): sized for a listing of about DEFAULT_GH_MAX_PAGINATED_PAGES pages of
# 100 items, not 100 pages of 30 s each.
DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS: float = 300.0
DEFAULT_GH_MAX_RETRIES: int = 2
DEFAULT_GH_RESOURCE: str = "core"
# `gh auth token` answers locally; a hung keyring must not stall the first gh or git call (#767).
DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS: float = 5.0
# After `gh auth token` printed no token, git runs without one and looks again only this much later;
# gh calls look again every time, since they cannot run without one.
DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS: float = 60.0
# A GitHub App installation token expires one hour after GitHub makes it. The process mints a new
# one when less than this is left, so a gh or git child that starts with the token can finish.
DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS: float = 600.0
DEFAULT_GH_CACHE_TTL_SECONDS: float = 60.0
DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC: int = 25
DEFAULT_GH_QUOTA_MAX_AGE_SECONDS: float = 300.0
# How long `gh api rate_limit` may run when the ledger refreshes a quota; past it the quota is
# left unread (#983).
DEFAULT_GH_QUOTA_REFRESH_TIMEOUT_SECONDS: float = 10.0
DEFAULT_GH_MAX_PAGINATED_PAGES: int = 100
DEFAULT_GH_REST_PER_PAGE: int = 100
# How many GET answers one GitHub session keeps with their ETags, in memory, for its next GET of
# the same URL to be conditional (#983). An entry is one answer: a page that links a next one, at
# most DEFAULT_GH_REST_PER_PAGE items, or a `rest()` GET's answer such as a pull request's diff; a
# page that links none is not kept. A roadmap poll's listings and a PR monitor's reads fit well
# inside it, and the URL read longest ago goes first.
DEFAULT_GH_SESSION_ETAG_CACHE_SIZE: int = 64
# Board reads page GraphQL's `ProjectV2.items` this many items at a time, its largest page (#1125).
DEFAULT_GH_PROJECT_ITEM_PAGE_SIZE: int = 100
# A board read stops before a page, and refuses before it starts, while GraphQL reports fewer
# points left than this: 5% of the 5,000-point hourly budget stays for the run's writes and for
# the other tools sharing the identity (#1125).
DEFAULT_GH_GRAPHQL_BUDGET_FLOOR: int = 250
# What one page of a board read is taken to cost before the run has read a page and measured it:
# GitHub charges a hundredth of the connection requests a query may make, rounded and at least 1,
# and a page of 100 items with their field values may make 101 (#1125).
DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS: int = 1
DEFAULT_GH_PROJECT_FIELD_LIMIT: int = 100
DEFAULT_GH_PROJECT_OPTION_COLOR: str = "GRAY"
# Closes and reopens read from one issue's timeline in one GraphQL request (#742).
DEFAULT_GH_ISSUE_TIMELINE_LIMIT: int = 100
# `devops roadmap intake` (#742): the nearest items the model judges, and how much of an issue's
# text it embeds and shows the model.
DEFAULT_ROADMAP_INTAKE_SHORTLIST: int = 5
DEFAULT_ROADMAP_INTAKE_TEXT_CHARS: int = 4000
DEFAULT_ROADMAP_INTAKE_EXCERPT_CHARS: int = 600
DEFAULT_ROADMAP_INTAKE_REASON_CHARS: int = 240
# `devops review intake` (#2420): the longest title of a candidate made from a review finding.
DEFAULT_REVIEW_INTAKE_TITLE_CHARS: int = 200
# The minutes between two runs of a row are prime numbers (#2965): no two rows keep the same
# poll tick for long, and no row lands on a multiple of 5 minutes.
DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES: int = 29
# How often refine is due on its own, besides its cross-job trigger (#1515).
DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES: int = 31
DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES: int = 13
DEFAULT_ROADMAP_MEMORY_REPO: str = "example/roadmap"
DEFAULT_ROADMAP_MEMORY_ACTOR: str = "devops-cli"
# The author of an issue the in-memory store opens: GitHub gives every issue an association.
DEFAULT_ROADMAP_MEMORY_AUTHOR_ASSOCIATION: str = "OWNER"
# The most items one refine round takes. It is the only cap of a round (#2004).
DEFAULT_ROADMAP_REFINE_LIMIT: int = 3
# The most candidates one Service round of intake decides, one model call each (#1360).
DEFAULT_ROADMAP_INTAKE_LIMIT: int = 5
# `devops roadmap alternatives` (#2650): the most items one run checks, and the days after which a
# check is old. The Service's row is due twice a day, about (#2652).
DEFAULT_ROADMAP_ALTERNATIVES_LIMIT: int = 5
DEFAULT_ROADMAP_ALTERNATIVES_RECHECK_DAYS: int = 30
DEFAULT_ROADMAP_ALTERNATIVES_RETRY_DAYS: int = 3
DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES: int = 719
# The PyPI JSON API reads of a package (`{name}` is one URL path segment) and its timeout.
DEFAULT_PYPI_PACKAGE_URL: str = "https://pypi.org/pypi/{name}/json"
DEFAULT_PYPI_TIMEOUT_SECONDS: float = 10.0
# The most items one stage run takes (#2654).
DEFAULT_ROADMAP_STAGE_LIMIT: int = 3
# The most extra turns of an implement step (#3043): each fixes a failed check or asks for ticks.
DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS: int = 3
# The most items one implement run takes, and the seconds between two reads of a pull request
# whose checks are not there yet (#2665).
DEFAULT_ROADMAP_IMPLEMENT_LIMIT: int = 1
DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS: int = 30
# How often the implement row is due on its own, besides its first run (#2667). A round only reads
# the Jobs and the plan; the Job itself runs for up to two hours.
DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES: int = 7
# The labels of the items the stage job takes when no setting and no option names others: every
# Ready item, of any type, priority, value and effort (#2906).
DEFAULT_ROADMAP_STAGE_FILTER: Final[tuple[str, ...]] = ("status=ready",)
# How often the stage row is due on its own, besides its first run and its cross-job trigger
# (#2659).
DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES: int = 37
# How often the stage_ready row is due on its own, besides its first run (#2865). A round with no
# recorded draft sends no request; a draft that waits for its checks costs two requests a round.
DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES: int = 3
# The tokens that the inputs of one implementation step may hold: the step's instructions, the
# `AGENTS.md` of the repository and the sections of the documents it routes the group to, the
# item, the change folder and the packed files of one task group. It leaves most of a 128k
# window for tool output and the model's turns (#2654).
DEFAULT_ROADMAP_STAGE_STEP_TOKENS: Final[int] = 40000
DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS: float = 1.0
DEFAULT_GH_SECONDARY_RATE_WAIT: float = 60.0
DEFAULT_GH_SECONDARY_MAX_CAP: float = 300.0
# The least a read the GitHub session retries after a 5xx waits; jittered exponential backoff is
# added to it. A server error is no rate limit, so it does not wait the secondary-limit floor.
DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS: float = 1.0
DEFAULT_GH_MAX_RATE_LIMIT_WAIT: float | None = None
# ── Kubernetes Falco Security Stream Defaults ─────────────────────────────────
DEFAULT_FALCO_NAMESPACE: str = "falco"
DEFAULT_FALCO_LABEL_SELECTOR: str = "app.kubernetes.io/name=falco"
DEFAULT_SECURITY_STREAM_DURATION_SECONDS: int = 30
DEFAULT_SECURITY_STREAM_TAIL_LINES: int = 100

# ── Threat Intelligence Distributed Caching Defaults ─────────────────────────
DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS: int = 86400  # 24 hours
DEFAULT_THREAT_INTEL_BATCH_SIZE: int = 25

# ── Kubernetes Informer & Service Defaults ───────────────────────────────────
DEFAULT_K8S_CACHE_TTL_SECONDS: float = 5.0
DEFAULT_K8S_INFORMER_RESYNC_SECONDS: float = 30.0
# Grace period granted to the informer worker thread to unwind after stop().
DEFAULT_K8S_INFORMER_STOP_TIMEOUT_SECONDS: float = 5.0
# Upper bound on cached watch objects, preventing unbounded growth on large clusters.
DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES: int = 10000
DEFAULT_K8S_INFORMER_BACKOFF_MIN_SECONDS: float = 1.0
DEFAULT_K8S_INFORMER_BACKOFF_MAX_SECONDS: float = 60.0
DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS: float = 5.0
DEFAULT_K8S_STREAM_TIMEOUT_SECONDS: float = 300.0

# ── Kubernetes Doctor Diagnostic Defaults ─────────────────────────────────────
DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES: int = 20
DEFAULT_K8S_DOCTOR_STUCK_SECONDS: int = 300
DEFAULT_K8S_DOCTOR_RESTART_THRESHOLD: int = 3
DEFAULT_K8S_DOCTOR_EVENT_COUNT_THRESHOLD: int = 5
# The Gitea stack checks (#2187): the bound of one kubectl read, of one request through the
# tunnel host, and of the curl that probes the pod's egress.
DEFAULT_K8S_DOCTOR_KUBECTL_TIMEOUT_SECONDS: float = 30.0
DEFAULT_K8S_DOCTOR_HTTP_TIMEOUT_SECONDS: float = 15.0
DEFAULT_K8S_DOCTOR_EGRESS_PROBE_SECONDS: int = 5

# ── Kubernetes Local-Path Volume Move Defaults (#2186) ───────────────────────
# GNU tar, findutils, coreutils, mawk and bash, with no package to install.
DEFAULT_K8S_VOLUME_MOVE_IMAGE: str = "debian:trixie-slim"
# A plain kubectl request: a read, a patch, a create, a scale or a delete without a wait.
DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS: float = 120.0
# How long `kubectl wait` waits for a pod to be Ready or gone, a delete and a claim to bind.
DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS: int = 300
# How long the workloads may take to be ready again after the move.
DEFAULT_K8S_VOLUME_MOVE_ROLLOUT_SECONDS: int = 600
# The bound of one copy and of one side's digest, which read every byte of the volume.
DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS: float = 3600.0
# The characters of kubectl's error output that a failure message keeps.
DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS: int = 400


# ── Dashboard TUI Defaults ──────────────────────────────────────────────────
# Retention ceiling for a streamed log view. A tail can emit hundreds of thousands
# of lines; memory is bounded by this rather than by how long the stream runs.
DEFAULT_LOG_BUFFER_MAX_LINES: int = 10000
# Lines rendered at once. Only this slice is handed to the widget per frame.
DEFAULT_LOG_VIEWPORT_LINES: int = 50
# Seconds between automatic dashboard refreshes.
DEFAULT_DASHBOARD_REFRESH_SECONDS: int = 5
# Age beyond which a domain snapshot is flagged as stale in the UI.
DEFAULT_DASHBOARD_STALE_SECONDS: float = 30.0
# Minimum seconds between log-pane redraws. A busy stream produces lines far faster than
# a terminal can usefully repaint; every line is still retained, only the drawing is
# coalesced, which is what keeps the UI thread free under load.
DEFAULT_LOG_REDRAW_INTERVAL_SECONDS: float = 0.05
# Most recent events the pod inspector lists for one pod.
DEFAULT_K8S_POD_EVENT_LIMIT: int = 20
# Pods `devops dashboard --summary` lists, unhealthy ones first; it counts the rest.
DEFAULT_DASHBOARD_SUMMARY_POD_ROWS: int = 10

# ── Telemetry Span Buffer ───────────────────────────────────────────────────
# Completed spans retained in memory for the waterfall view and offline inspection.
# Bounded so a long-running command cannot grow the buffer without limit.
DEFAULT_SPAN_BUFFER_MAX_SPANS: int = 1000

# ── Dashboard Provider Timeouts ─────────────────────────────────────────────
# Kept short: these run per refresh, and a panel that blocks is the failure the threaded
# refresh architecture exists to prevent.
DEFAULT_VALKEY_PANEL_TIMEOUT_SECONDS: float = 1.0
DEFAULT_TELEMETRY_QUERY_TIMEOUT_SECONDS: float = 3.0
# Timeout for requests proxied through the Kubernetes API server. The extra hop makes these
# a little slower than a direct call, but they must still not block a dashboard refresh.
DEFAULT_K8S_PROXY_TIMEOUT_SECONDS: float = 5.0

# ── Valkey Pipeline Batching ────────────────────────────────────────────────
# A pipeline is serialized into one buffer before it is written, so an unbounded batch
# costs memory proportional to the batch; the client sends at most this many commands per
# round trip.
DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS: int = 1000
# How long the log consumer waits for a line before re-checking whether it should stop.
# Short enough that quitting feels immediate on a silent stream.
DEFAULT_LOG_STREAM_POLL_SECONDS: float = 0.1
# How long a compiled .gitignore is trusted before its modification time is checked again.
# Stat-ing every ignore file on every check dominated the cost of a repository walk; an
# edit is still picked up within this window.
DEFAULT_GITIGNORE_REVALIDATE_SECONDS: float = 2.0

# ── Shared HTTP Connection Pooling ──────────────────────────────────────────
# Reusing connections without a ceiling trades connection churn for descriptor exhaustion.
DEFAULT_HTTP_MAX_CONNECTIONS: int = 100
DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 20
# Idle connections are dropped after this long. Long enough to span a burst of agent calls,
# short enough that an endpoint restarting does not leave the pool holding dead sockets.
DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS: float = 30.0

# The most lines of a finding's location a session records as its cited excerpt (#950). A
# finding's range is a few lines; a model that cites a whole file should not copy it into every
# session file and dataset record.
DEFAULT_CITED_EXCERPT_MAX_LINES: Final[int] = 40

# How long a stopped background command's process group has to exit after SIGTERM before its
# remaining members get SIGKILL, and how often the group is probed meanwhile (#958).
DEFAULT_SHELL_STOP_GRACE_SECONDS: Final[float] = 3.0
DEFAULT_SHELL_STOP_POLL_SECONDS: Final[float] = 0.05

# ── Service Mode Defaults ─────────────────────────────────────────────────────
DEFAULT_SERVICE_POLL_INTERVAL_SECONDS: Final[int] = 151
DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS: Final[int] = 120
# The GitHub requests the Service sends in any one hour, all repositories together (#2161). GitHub
# suspended the roadmap's former machine account at 800 to 1,700 requests an hour, so the default
# stays under that.
DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR: Final[int] = 500
# How many rounds in a row a roadmap job may fail before the Service stops running it until its
# input changes (#2161).
DEFAULT_SERVICE_MAX_FAILED_ROUNDS: Final[int] = 3
# The most model calls the Service keeps in flight at once. The Service's model tier serves one
# call at a time, so one keeps a lane's call from queueing at the gateway, where a stall timer
# would refuse it, and lets it wait in the Service instead (#2564).
DEFAULT_SERVICE_MODEL_CALL_CONCURRENCY: Final[int] = 1

# ── AI Research Information Foraging Defaults ────────────────────────────────
DEFAULT_AI_FORAGE_MAX_NODES: Final[int] = 20
DEFAULT_AI_FORAGE_MIN_SCORE: Final[float] = 0.1
DEFAULT_AI_FORAGE_MAX_COMMITS: Final[int] = 50
DEFAULT_AI_FORAGE_FILE_READ_CAP_BYTES: Final[int] = 65536

# ── AI Research Socratic Inquiry Defaults ─────────────────────────────────────
DEFAULT_AI_SOCRATIC_MAX_PROBES: Final[int] = 5

# ── AI Research Mental Model Defaults ─────────────────────────────────────────
DEFAULT_AI_RESEARCH_DIR: Final[str] = ".data/research"

# ── AI Research Analogies Defaults ─────────────────────────────────────────────
DEFAULT_AI_ANALOGIES_MIN_SCORE: Final[float] = 0.5
DEFAULT_AI_ANALOGIES_LIMIT: Final[int] = 10

# ── LLM Gateway Tuning & Rendering Defaults ─────────────────────────────────
# The gateway's LiteLLM config; k8s/llm/gateway/kustomization.yaml generates its ConfigMap from it.
DEFAULT_LLM_GATEWAY_CONFIG_PATH: Final[Path] = Path("k8s/llm/gateway/config.yaml")
DEFAULT_LLM_PROFILES_PATH: Final[Path] = Path("k8s/llm/profiles/ollama-profiles.yaml")
DEFAULT_LLM_SERVICES_PATH: Final[Path] = Path("k8s/llm/profiles/services.yaml")

# ── Review Finding Group Model Analysis Defaults (#1147) ────────────────────
DEFAULT_ANALYSIS_ANCHOR_CONTEXT_LINES: Final[int] = 10
DEFAULT_ANALYSIS_REFERENCE_BUDGET_CHARS: Final[int] = 16000
DEFAULT_ANALYSIS_SAMPLING_SEED: Final[int] = 42
DEFAULT_ANALYSIS_PYTHON_FLOOR: Final[str] = "py314"

# ── Cloudflare API Retry Defaults (#1436) ─────────────────────────────────────
DEFAULT_CLOUDFLARE_MAX_RETRIES: Final[int] = 3
DEFAULT_CLOUDFLARE_RETRY_MIN_WAIT: Final[float] = 1.0
DEFAULT_CLOUDFLARE_RETRY_MAX_WAIT: Final[float] = 30.0
