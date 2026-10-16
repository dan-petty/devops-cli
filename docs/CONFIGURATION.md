# DevOps CLI Configuration Reference

This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).

DevOps CLI supports hierarchical configuration resolution through:
1. **CLI Flags & Arguments** (highest precedence)
2. **Environment Variables** (`DEVOPS_CLI_*`)
3. **Local Project Configuration** (the file `DEVOPS_CLI_CONFIG` names, else the nearest `config.yaml`, `.devcontainer/config.yaml`, `.devops/config.yaml`, `.devops.yaml` or `.devcontainer/.devops.yaml` from the working directory up to its repository root)
4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)
5. **System Defaults**

A `devops review` command reads a tree it does not own. Started in a repository other than devops-cli's own, it looks for no project configuration, reading only the file `DEVOPS_CLI_CONFIG` names, and it resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. What a review keeps -- its sessions, the feedback dataset, runs, samples, library contracts and AI spend -- every other command started outside devops-cli's own repository reads and writes there too. devops-cli's own repository is the one whose checkout holds the source of the devops-cli that runs, as an editable install's does; its code already runs, so a review started there, or in any worktree of it, reads its project configuration and keeps all data under its main worktree's `.data`, as every other command does. A clone nested in that checkout is another repository, and an installed devops-cli trusts no repository this way. An absolute `DEVOPS_CLI_DATA_DIR` or `data.dir` names the data directory every command uses.

---

## GitHub Configuration (`github`)

GitHub authentication, default owner, and repository settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `default_org` | `Union` | - | `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | - |

## SSH Configuration (`ssh`)

SSH key generation, rotation, signing, and GitHub registration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `key_dir` | `Path` | `~/.ssh` | `DEVOPS_CLI_SSH_KEY_DIR` | - |
| `key_prefix` | `Union` | - | `DEVOPS_CLI_SSH_KEY_PREFIX` | - |
| `rotation_days` | `int` | `90` | `DEVOPS_CLI_SSH_ROTATION_DAYS` | - |

## Repositories Configuration (`repos`)

Multi-repository workspace discovery, cloning, and sync settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `base_dir` | `Path` | `repos` | `DEVOPS_CLI_REPOS_BASE_DIR` | - |

## Workspace Configuration (`workspace`)

Multi-root VS Code workspace file management and data tier settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `file` | `Path` | `.code-workspace` | `DEVOPS_CLI_WORKSPACE_FILE` | - |

## Grafana Configuration (`grafana`)

Grafana endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_GRAFANA_URL` | - |

## Prometheus Configuration (`prometheus`)

Prometheus query endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_PROMETHEUS_URL` | - |

## Argo CD Configuration (`argocd`)

Argo CD server endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_ARGOCD_URL` | - |

## Qdrant Vector Store (`qdrant`)

The vector store that RAG searches query and indexing writes to.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `http://localhost:6333` | `DEVOPS_CLI_QDRANT_URL` | - |
| `collection_prefix` | `str` | `devops` | `DEVOPS_CLI_QDRANT_COLLECTION_PREFIX` | - |
| `api_key` | `Union` | - | `DEVOPS_CLI_QDRANT_API_KEY` | - |
| `timeout` | `float` | `300.0` | `DEVOPS_CLI_QDRANT_TIMEOUT` | Seconds each Qdrant request waits per attempt: RAG searches, and indexing's upserts and deletes, which share the client |

## Valkey Configuration (`valkey`)

Valkey caching endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `host` | `str` | `localhost:6379` | `DEVOPS_CLI_VALKEY_HOST` | - |
| `port` | `int` | `6379` | `DEVOPS_CLI_VALKEY_PORT` | - |
| `url` | `Union` | - | - | - |
| `password` | `Union` | - | `DEVOPS_CLI_VALKEY_PASSWORD` | - |
| `db` | `int` | `0` | `DEVOPS_CLI_VALKEY_DB` | - |
| `timeout` | `float` | `2.0` | `DEVOPS_CLI_VALKEY_TIMEOUT` | - |
| `threat_intel_ttl` | `int` | `86400` | - | - |

## Shared Run Index (`runs`)

PostgreSQL connection settings for the shared AI run index.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `index_url` | `Union` | - | `DEVOPS_CLI_RUNS_INDEX_URL` | - |

## Tempo Configuration (`tempo`)

Grafana Tempo distributed tracing query endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `http://localhost:3200` | - | - |

## Pyroscope Configuration (`pyroscope`)

Grafana Pyroscope continuous profiling endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `http://localhost:4040` | - | - |

## Telemetry & Metrics (`telemetry`)

OpenTelemetry export and Logfire settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `enabled` | `bool` | `True` | `DEVOPS_CLI_TELEMETRY_ENABLED` | Export OpenTelemetry traces and metrics |
| `endpoint` | `Union` | - | `DEVOPS_CLI_TELEMETRY_ENDPOINT` | OpenTelemetry collector that traces and metrics go to; unset, `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318` |
| `logfire` | `bool` | `False` | - | - |
| `logfire_token` | `Union` | - | - | - |
| `logfire_send_to_logfire` | `Union` | `if-token-present` | - | - |

## Kubernetes Configuration (`k8s`)

Kubernetes context, ingress domain, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `context` | `str` | `minikube` | `DEVOPS_CLI_K8S_CONTEXT` | Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context) |
| `domain` | `Union` | - | `DEVOPS_CLI_K8S_DOMAIN` | Base domain name for homelab ingress routes and tunnel services (e.g. example.com) |
| `addressing` | `Union` | - | - | Default addressing mode for cluster services: nodeport, proxy, or fqdn. |
| `github_account` | `Union` | - | `DEVOPS_CLI_K8S_GITHUB_ACCOUNT` | Login of the machine account whose gh token `devops k8s push-secrets` writes to the cluster as GH_TOKEN; `--github-account` overrides it |

## Cloudflare Configuration (`cloudflare`)

Cloudflare API token and zone settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_DOMAIN` | Root or zone domain name managed in Cloudflare (e.g. example.com) |
| `tunnel` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_TUNNEL` | Cloudflare tunnel name or identifier (e.g. homelab) |
| `account_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| `zone_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
| `public_ip_bypass` | `Union` | - | - | Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication |
| `access` | `CloudflareAccessConfig` | `enabled=False allowed_emails=[] idp='google' bypass_ips=[] public_ip_bypass=None` | - | Cloudflare Zero Trust Access application and policy configuration |

## Sandbox Configuration (`sandbox`)

Isolated container sandbox runtime, resource limits, and network policy settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `exclude_home_dir` | `bool` | `True` | - | Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*) |

## AI & LLM Configuration (`ai`)

AI code review, multi-agent pipelines, RAG semantic search, and embeddings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `provider` | `str` | `ollama` | `DEVOPS_CLI_AI_PROVIDER` | - |
| `model` | `str` | `gemma4:26b` | `DEVOPS_CLI_AI_MODEL` | - |
| `reference_model` | `str` | `gpt-4o-mini` | - | - |
| `hardware_cost_usd` | `float` | `0.0` | - | - |
| `reasoning_effort` | `Union` | - | `DEVOPS_CLI_AI_REASONING_EFFORT` | - |
| `temperature` | `float` | `0.1` | - | - |
| `top_p` | `float` | `0.95` | - | - |
| `context_window` | `int` | `32768` | - | - |
| `num_ctx` | `Union` | - | - | - |
| `max_tokens` | `Union` | - | - | - |
| `ollama_urls` | `list` | `['http://localhost:11434']` | `DEVOPS_CLI_AI_OLLAMA_URLS` | - |
| `ollama_max_parallel` | `int` | `2` | `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | - |
| `gateway_provider` | `str` | `litellm` | - | - |
| `gateway_url` | `str` | `http://localhost:4000/v1` | - | - |
| `gateway_enabled` | `bool` | `False` | - | - |
| `gateway_weights` | `dict` | `{}` | - | - |
| `gateway_concurrency` | `dict` | `{}` | - | - |
| `portkey_url` | `str` | `http://localhost:8787/v1` | - | - |
| `api_base_url` | `Union` | - | `DEVOPS_CLI_AI_API_BASE_URL` | - |
| `allow_private_network` | `bool` | `False` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | - |
| `max_retries` | `int` | `4` | `DEVOPS_CLI_AI_MAX_RETRIES` | - |
| `timeout` | `Union` | - | - | Seconds each LLM request waits for its reply; `ai.tasks.<task>.timeout` sets one task's. Unset, a request waits 3600 s, and a review's analysis requests 1200 s |
| `tasks` | `AITasksConfig` | `chat=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) metadata=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) analysis=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) embedding=AITaskOverride(provider=None, model='qwen3-embedding:0.6b', reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None)` | - | - |
| `rag` | `AIRAGConfig` | `enabled=True top_k=5 score_threshold=0.35 chunk_size=2400 chunk_overlap=240` | - | - |
| `cache` | `AICacheConfig` | `enabled=True backend='file' dir=PosixPath('.data/cache/llm') ttl_seconds=604800 max_entries=1000 append_cache=False` | - | - |
| `durable` | `AIDurableConfig` | `engine='sqlite' store_path=PosixPath('.data/durable_runs.db') task_queue='devops-cli-tasks' workflow_id_prefix='devops-run-'` | - | - |
| `task_name` | `Union` | - | - | - |

## Open WebUI Configuration (`open_webui`)

Open WebUI endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Data Storage Tier (`data`)

Local artifact caches, review findings, session histories, and log paths.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `dir` | `Path` | `.data` | `DEVOPS_CLI_DATA_DIR` | - |
| `analysis_dir` | `Path` | `.data/analysis` | `DEVOPS_CLI_DATA_ANALYSIS_DIR` | - |
| `reviews_dir` | `Path` | `.data/reviews` | `DEVOPS_CLI_DATA_REVIEWS_DIR` | - |
| `logs_dir` | `Path` | `.data/logs` | `DEVOPS_CLI_DATA_LOGS_DIR` | - |
| `models_dir` | `Path` | `.data/models` | `DEVOPS_CLI_DATA_MODELS_DIR` | - |
| `cache_dir` | `Path` | `.data/cache` | `DEVOPS_CLI_DATA_CACHE_DIR` | - |
| `benchmarks_dir` | `Path` | `.data/benchmarks` | `DEVOPS_CLI_DATA_BENCHMARKS_DIR` | - |
| `rag_dir` | `Path` | `.data/rag` | `DEVOPS_CLI_DATA_RAG_DIR` | - |
| `samples_dir` | `Path` | `.data/samples` | `DEVOPS_CLI_DATA_SAMPLES_DIR` | - |
| `runs_dir` | `Path` | `.data/runs` | `DEVOPS_CLI_DATA_RUNS_DIR` | - |
| `tls_dir` | `Path` | `.data/tls` | `DEVOPS_CLI_DATA_TLS_DIR` | - |
| `audit_log_path` | `Path` | `.data/logs/audit.jsonl` | `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | - |
| `feedback_dataset_path` | `Path` | `.data/feedback_dataset.jsonl` | `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | - |

## Service Configuration (`service`)

In-cluster webhook receiver and background job runner settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `repos` | `list` | `[]` | `DEVOPS_CLI_SERVICE_REPOS` | - |
| `machine_account` | `Union` | - | `DEVOPS_CLI_SERVICE_MACHINE_ACCOUNT` | - |
| `poll_interval_seconds` | `int` | `300` | `DEVOPS_CLI_SERVICE_POLL_INTERVAL_SECONDS` | - |
| `drain_timeout_seconds` | `int` | `120` | `DEVOPS_CLI_SERVICE_DRAIN_TIMEOUT_SECONDS` | - |

## Tavily Search Configuration (`tavily`)

Tavily web search API authentication settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `api_key` | `Union` | - | `DEVOPS_CLI_TAVILY_API_KEY` | - |

## Top-Level Settings

Top-level workstation and environment settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | - | Default domain name for the environment or workstation |
