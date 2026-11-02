# DevOps CLI Configuration Reference

This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).

DevOps CLI supports hierarchical configuration resolution through:
1. **CLI Flags & Arguments** (highest precedence)
2. **Environment Variables** (`DEVOPS_CLI_*`)
3. **Local Project Configuration** (the file `DEVOPS_CLI_CONFIG` names, else the nearest `config.yaml`, `.devcontainer/config.yaml`, `.devops/config.yaml`, `.devops.yaml` or `.devcontainer/.devops.yaml` from the working directory up to its repository root)
4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)
5. **System Defaults**

`setting_sources` in `src/devops_cli/config/settings.py` declares the order of items 2 to 5 one time, as pydantic-settings sources. A setting takes the value of the first source that holds it, and only that value is checked against the type of the setting: a value that a variable replaces is not checked. A null in the project file is no value, so the value of the global file stays. A config file whose document is not a mapping of keys to values stops the load with an error that names the file. `DEVOPS_CLI_DATA_DIR` also moves each data path that no variable of its own sets into that directory, so the data paths of a config file do not apply. A credential resolves in its own order: the OS keyring, Vault, its variable, and last the config file, for a credential that a config file can hold.

A `devops review` command reads a tree it does not own. Started in a repository other than devops-cli's own, it looks for no project configuration, reading only the file `DEVOPS_CLI_CONFIG` names, and it resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. What a review keeps -- its sessions, the feedback dataset, runs, samples, library contracts and AI spend -- every other command started outside devops-cli's own repository reads and writes there too. devops-cli's own repository is the one whose checkout holds the source of the devops-cli that runs, as an editable install's does; its code already runs, so a review started there, or in any worktree of it, reads its project configuration and keeps all data under its main worktree's `.data`, as every other command does. A clone nested in that checkout is another repository, and an installed devops-cli trusts no repository this way. An absolute `DEVOPS_CLI_DATA_DIR` or `data.dir` names the data directory every command uses.

A command that saves settings, such as `devops config set`, writes the file `DEVOPS_CLI_CONFIG` names, else the project configuration it finds, else the global one. It writes only the keys whose values the command changed, and it keeps the comments, the order of the keys and the keys that devops-cli does not know. A default, or a value that the other config file or an environment variable gives, stays out of the file, but `devops config set` writes the key that it names also when the value does not change. Before it changes the file, it copies the file to `<name>.bak-<YYYYMMDD-HHMMSS>` in the same directory, with the time in UTC, and keeps the newest 10 copies. Then it appends a record to the audit log (`data.audit_log_path`) with the command and the dotted names of the keys that changed, never a value. A save that changes no byte of the file writes nothing.

`devops config unset <key>` removes a key and its value from the same file, with the same copy and audit record. It edits the file and loads no settings, and `--dry-run` prints the change, with the lines of its unified diff, and writes nothing. The `ai` section and each section under it refuse a key that they do not declare. Such a key stops every command that loads the settings, with an error that names the full dotted key, its file and line, the release that removed the key when devops-cli knows it, and the `devops config unset` command that removes it.

To edit another file, run `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`. `devops config audit-keys` names this command for each plaintext secret that it finds. Store a credential before you remove it: use `devops config set <key>`, with `--from-file <path>` for a multi-line one. The copy of the file, and each older copy, shows a credential that the command removes as `***REDACTED***`, so no copy holds its value.

`devops config set` takes a key that names a settings field with a value, or a credential. For any other key, it exits 1 with `Unknown config key: '<key>'` before it asks for a value or reads a file, and names the known keys with a similar name. `devops config get` gives the same message for a key that it cannot find.

---

## GitHub Configuration (`github`)

GitHub authentication, default owner, and repository settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `default_org` | `Union` | - | `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | Default GitHub organization |

## SSH Configuration (`ssh`)

SSH key generation, rotation, signing, and GitHub registration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `key_dir` | `Path` | `~/.ssh` | `DEVOPS_CLI_SSH_KEY_DIR` | Directory for SSH key pairs |
| `key_prefix` | `Union` | - | `DEVOPS_CLI_SSH_KEY_PREFIX` | Prefix for generated SSH keys (defaults to devcontainer name or basename pwd) |
| `rotation_days` | `int` | `90` | `DEVOPS_CLI_SSH_ROTATION_DAYS` | SSH key rotation interval in days |

## Repositories Configuration (`repos`)

Multi-repository workspace discovery, cloning, and sync settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `base_dir` | `Path` | `repos` | `DEVOPS_CLI_REPOS_BASE_DIR` | Base directory for cloned repositories |

## Workspace Configuration (`workspace`)

Multi-root VS Code workspace file management and data tier settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `file` | `Path` | `.code-workspace` | `DEVOPS_CLI_WORKSPACE_FILE` | Path to VS Code workspace file |

## Grafana Configuration (`grafana`)

Grafana endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_GRAFANA_URL` | Grafana service URL |

## Prometheus Configuration (`prometheus`)

Prometheus query endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_PROMETHEUS_URL` | Prometheus service URL |

## Argo CD Configuration (`argocd`)

Argo CD server endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_ARGOCD_URL` | ArgoCD service URL |
| `github_app_id` | `Union` | - | `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` | ID of the GitHub App that Argo CD's GitHub notifier acts as |
| `github_app_installation_id` | `Union` | - | `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` | ID of the installation of Argo CD's notifier App on the managed repositories |

## Qdrant Vector Store (`qdrant`)

The vector store that RAG searches query and indexing writes to.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_QDRANT_URL` | Qdrant vector database server URL |
| `collection_prefix` | `str` | `devops` | `DEVOPS_CLI_QDRANT_COLLECTION_PREFIX` | Prefix for Qdrant collection names |
| `api_key` | `Union` | - | `DEVOPS_CLI_QDRANT_API_KEY` | - |
| `timeout` | `float` | `300.0` | `DEVOPS_CLI_QDRANT_TIMEOUT` | Seconds each Qdrant request waits per attempt: RAG searches, and indexing's upserts and deletes, which share the client |

## Valkey Configuration (`valkey`)

Valkey caching endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `valkey://localhost:6379/0` | `DEVOPS_CLI_VALKEY_URL` | The Valkey endpoint, such as `valkeys://example.com:6380/0`: the scheme, the host, the port and the database. The scheme `valkeys` connects over TLS and checks the certificate against the host. The scheme `valkey` connects in plaintext. The URL holds no password: `valkey.password` is in the OS keyring |
| `password` | `Union` | - | `DEVOPS_CLI_VALKEY_PASSWORD` | - |
| `timeout` | `float` | `2.0` | `DEVOPS_CLI_VALKEY_TIMEOUT` | Valkey network socket connection/read timeout in seconds; the shared cache of embeddings, threat intel and library symbols waits at most 0.25 s for a connection (default: 2.0) |
| `threat_intel_ttl` | `int` | `86400` | - | - |

## Shared Run Index (`runs`)

PostgreSQL connection settings for the shared AI run index.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `index_url` | `Union` | - | `DEVOPS_CLI_RUNS_INDEX_URL` | Valkey holding the run index shared by workstations (set by `devops ai runs connect`) |

## Tempo Configuration (`tempo`)

Grafana Tempo distributed tracing query endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Pyroscope Configuration (`pyroscope`)

Grafana Pyroscope continuous profiling endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Telemetry & Metrics (`telemetry`)

OpenTelemetry export and Logfire settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `enabled` | `bool` | `True` | `DEVOPS_CLI_TELEMETRY_ENABLED` | Export OpenTelemetry traces and metrics |
| `endpoint` | `Union` | - | `DEVOPS_CLI_TELEMETRY_ENDPOINT` | OpenTelemetry collector that traces and metrics go to; unset, `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318` |
| `capture_command_args` | `bool` | `False` | - | Record the arguments of each program that devops-cli runs in `process.command_args` on its subprocess span, each argument through the secret mask. Off by default: an argument can be a credential that the mask does not find |
| `capture_llm_content` | `bool` | `False` | `DEVOPS_CLI_TELEMETRY_CAPTURE_LLM_CONTENT` | Record LLM prompt and reply text in OpenTelemetry and Logfire telemetry spans. Off by default to prevent exposure of sensitive data |
| `logfire` | `bool` | `False` | - | - |
| `logfire_token` | `Union` | - | `DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN` | - |
| `logfire_send_to_logfire` | `Union` | `if-token-present` | - | - |

## Kubernetes Configuration (`k8s`)

Kubernetes context, ingress domain, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `context` | `str` | `minikube` | `DEVOPS_CLI_K8S_CONTEXT` | Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context) |
| `domain` | `Union` | - | `DEVOPS_CLI_K8S_DOMAIN` | Base domain name for homelab ingress routes and tunnel services (e.g. example.com) |
| `tunnel_host` | `Union` | - | `DEVOPS_CLI_K8S_TUNNEL_HOST` | Hostname of the Kubernetes API route through the Cloudflare tunnel, which 'devops k8s tunnel start' forwards to a local port (e.g. k8s.example.com) |
| `addressing` | `Union` | - | - | Default addressing mode for cluster services: nodeport, proxy, or fqdn. |

## Cloudflare Configuration (`cloudflare`)

Cloudflare API token and zone settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_DOMAIN` | Root or zone domain name managed in Cloudflare (e.g. example.com) |
| `tunnel` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_TUNNEL` | Cloudflare tunnel name or identifier (e.g. homelab) |
| `account_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| `zone_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
| `public_ip_bypass` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_PUBLIC_IP_BYPASS` | Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication |
| `access` | `CloudflareAccessConfig` | `allowed_emails=[] bypass_ips=[] public_ip_bypass=None` | - | Cloudflare Zero Trust Access application and policy configuration |

## Sandbox Configuration (`sandbox`)

Isolated container sandbox runtime, resource limits, and network policy settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `exclude_home_dir` | `bool` | `True` | `DEVOPS_CLI_SANDBOX_EXCLUDE_HOME_DIR` | Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*) |

## CI Gate Configuration (`ci`)

Limit on how many CPU-heavy `devops ci` gates run at once on one host.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `gate_slots` | `Union` | - | `DEVOPS_CLI_CI_GATE_SLOTS` | Number of CPU-heavy devops ci gates that run at once on this host (default: one for each 16 CPUs) |

## AI & LLM Configuration (`ai`)

AI code review, multi-agent pipelines, RAG semantic search, and embeddings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `provider` | `str` | `ollama` | `DEVOPS_CLI_AI_PROVIDER` | AI provider (ollama | claude | copilot | openai) |
| `model` | `str` | `qwen3.8:27b` | `DEVOPS_CLI_AI_MODEL` | Default AI model name |
| `api_key` | `Union` | - | `DEVOPS_CLI_AI_API_KEY` | - |
| `reference_model` | `str` | `gpt-4o` | `DEVOPS_CLI_AI_REFERENCE_MODEL` | Hosted chat model whose genai-prices price values the local chat tokens in the AI spend reports |
| `reference_embedding_model` | `str` | `text-embedding-3-small` | `DEVOPS_CLI_AI_REFERENCE_EMBEDDING_MODEL` | Hosted embedding model whose genai-prices price values the local embedding tokens in the AI spend reports |
| `reference_provider` | `str` | `openai` | `DEVOPS_CLI_AI_REFERENCE_PROVIDER` | Provider in genai-prices of the two reference models |
| `hardware_cost_usd` | `float` | `0.0` | `DEVOPS_CLI_AI_HARDWARE_COST_USD` | Cost in USD of the local AI hardware, which `devops ai cost` compares with the savings |
| `reasoning_effort` | `Union` | - | `DEVOPS_CLI_AI_REASONING_EFFORT` | AI reasoning effort level (low | medium | high) |
| `supports_reasoning` | `bool` | `False` | - | - |
| `use_model_sampling` | `bool` | `False` | - | Leave sampling parameters to the model. When true, requests carry neither temperature, top_p nor seed. |
| `temperature` | `float` | `0.1` | - | - |
| `top_p` | `float` | `0.95` | - | - |
| `context_window` | `int` | `32768` | - | - |
| `num_ctx` | `Union` | - | - | - |
| `max_tokens` | `Union` | - | - | - |
| `ollama_urls` | `list` | `[]` | `DEVOPS_CLI_AI_OLLAMA_URLS` | Ollama service URLs (comma-separated) |
| `ollama_max_parallel` | `int` | `2` | `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | Maximum parallel requests per Ollama host |
| `gateway_provider` | `str` | `litellm` | - | - |
| `gateway_url` | `Union` | - | `DEVOPS_CLI_AI_GATEWAY_URL` | AI gateway URL |
| `gateway_enabled` | `bool` | `False` | - | - |
| `gateway_weights` | `dict` | `{}` | - | - |
| `gateway_concurrency` | `dict` | `{}` | - | - |
| `portkey_url` | `Union` | - | - | - |
| `api_base_url` | `Union` | - | `DEVOPS_CLI_AI_API_BASE_URL` | AI API base URL |
| `allow_private_network` | `bool` | `False` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | Permit private-IP network targets |
| `max_retries` | `int` | `4` | `DEVOPS_CLI_AI_MAX_RETRIES` | Maximum retry count for AI requests upon response validation failure |
| `timeout` | `Union` | - | - | Seconds each LLM request waits for the next data of its reply: a streamed reply, such as every OpenAI-compatible chat reply, can take longer in total. `ai.tasks.<task>.timeout` sets one task's. Unset, a request waits 3600 s, and a review's analysis requests 1200 s |
| `tasks` | `AITasksConfig` | `chat=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) metadata=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) analysis=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) verification=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) compose=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) embedding=AIEmbeddingTaskOverride(provider=None, model='qwen3-embedding:0.6b', reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) implement=AIImplementTaskOverride(provider=None, model='devops-coder', reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=128000, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) triage=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None)` | - | - |
| `rag` | `AIRAGConfig` | `enabled=True top_k=5 score_threshold=0.35 chunk_size=2400 chunk_overlap=240` | - | - |
| `cache` | `AICacheConfig` | `enabled=True ttl_seconds=604800 max_entries=1000 append_cache=False` | - | - |
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
| `dir` | `Path` | `.data` | `DEVOPS_CLI_DATA_DIR` | Root data directory for local reviews, cache, logs, and artifacts (default: ./.data; outside devops-cli's own repository, ~/.local/share/devops-cli/.data for review data and a `devops review` command) |
| `analysis_dir` | `Path` | `.data/analysis` | `DEVOPS_CLI_DATA_ANALYSIS_DIR` | Storage directory for pre-analysis metadata JSON files |
| `reviews_dir` | `Path` | `.data/reviews` | `DEVOPS_CLI_DATA_REVIEWS_DIR` | Storage directory for review session finding reports and artifacts |
| `logs_dir` | `Path` | `.data/logs` | `DEVOPS_CLI_DATA_LOGS_DIR` | Storage directory for CLI execution and SIEM audit logs |
| `models_dir` | `Path` | `.data/models` | `DEVOPS_CLI_DATA_MODELS_DIR` | Storage directory for local model checkpoints and weights |
| `cache_dir` | `Path` | `.data/cache` | `DEVOPS_CLI_DATA_CACHE_DIR` | Storage directory for local response and retrieval cache |
| `benchmarks_dir` | `Path` | `.data/benchmarks` | `DEVOPS_CLI_DATA_BENCHMARKS_DIR` | Storage directory for benchmark test runs and embedding leaderboard reports |
| `rag_dir` | `Path` | `.data/rag` | `DEVOPS_CLI_DATA_RAG_DIR` | Storage directory for local vector embedding index cache and retrieval data |
| `samples_dir` | `Path` | `.data/samples` | `DEVOPS_CLI_DATA_SAMPLES_DIR` | Storage directory for open-source sample repositories fetched at their pinned commits |
| `runs_dir` | `Path` | `.data/runs` | `DEVOPS_CLI_DATA_RUNS_DIR` | Storage directory for benchmark and evaluation run records, the run store's source of truth |
| `tls_dir` | `Path` | `.data/tls` | `DEVOPS_CLI_DATA_TLS_DIR` | Storage directory for generated local CA and TLS certificates |
| `audit_log_path` | `Path` | `.data/logs/audit.jsonl` | `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | Path to structured audit JSONL log file |
| `feedback_dataset_path` | `Path` | `.data/feedback_dataset.jsonl` | `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | Path to feedback fine-tuning dataset JSONL file |

## Service Configuration (`service`)

In-cluster webhook receiver and background job runner settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `repos` | `list` | `[]` | `DEVOPS_CLI_SERVICE_REPOS` | Target repository list for service mode |
| `github_app` | `GitHubAppConfig` | `app_id=None installation_id=None slug=None token_repository=None` | - | - |
| `poll_interval_seconds` | `int` | `151` | `DEVOPS_CLI_SERVICE_POLL_INTERVAL_SECONDS` | Periodic polling interval for service mode in seconds |
| `drain_timeout_seconds` | `int` | `120` | `DEVOPS_CLI_SERVICE_DRAIN_TIMEOUT_SECONDS` | Shutdown drain timeout for running service jobs in seconds |
| `github_requests_per_hour` | `int` | `500` | `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | The most GitHub requests the Service sends in one hour; a request that the last hour has no room for waits. The alert RoadmapServiceGitHubRequestsHigh follows this limit |
| `model_call_concurrency` | `int` | `1` | `DEVOPS_CLI_SERVICE_MODEL_CALL_CONCURRENCY` | The most model calls the Service keeps in flight at once; a lane that waits does so in the Service, where no stall timer runs |

## Roadmap Configuration (`roadmap`)

roadmap configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `alternatives` | `AlternativesConfig` | `limit=5 recheck_days=30 retry_days=3` | - | - |
| `stage` | `RoadmapStageConfig` | `filter=['status=ready'] limit=3 step_tokens=40000` | - | - |
| `implement` | `RoadmapImplementConfig` | `in_runner=False repair_rounds=3` | - | - |

## Firecrawl Configuration (`firecrawl`)

Firecrawl web search API authentication settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `api_key` | `Union` | - | `DEVOPS_CLI_FIRECRAWL_API_KEY` | - |

## Top-Level Settings

Top-level workstation and environment settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | - | Default domain name for the environment or workstation |
