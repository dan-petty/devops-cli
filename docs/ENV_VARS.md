# Configuration Environment Variables

All configuration options for `devops-cli` can be overridden via environment variables or loaded from OS Keyring for sensitive secrets.

| Environment Variable | Config Key | Secret | Description |
|---|---|---|---|
| `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | `ai.allow_private_network` | No | Permit private-IP network targets |
| `DEVOPS_CLI_AI_API_BASE_URL` | `ai.api_base_url` | No | AI API base URL |
| `DEVOPS_CLI_AI_API_KEY` | `ai.api_key` | 🔒 Yes | AI API key (stored in OS keyring) |
| `DEVOPS_CLI_AI_GATEWAY_URL` | `ai.gateway_url` | No | AI gateway URL |
| `DEVOPS_CLI_AI_HARDWARE_COST_USD` | `ai.hardware_cost_usd` | No | Cost in USD of the local AI hardware, which `devops ai cost` compares with the savings |
| `DEVOPS_CLI_AI_MAX_RETRIES` | `ai.max_retries` | No | Maximum retry count for AI requests upon response validation failure |
| `DEVOPS_CLI_AI_MODEL` | `ai.model` | No | Default AI model name |
| `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | `ai.ollama_max_parallel` | No | Maximum parallel requests per Ollama host |
| `DEVOPS_CLI_AI_OLLAMA_URLS` | `ai.ollama_urls` | No | Ollama service URLs (comma-separated) |
| `DEVOPS_CLI_AI_PROVIDER` | `ai.provider` | No | AI provider (ollama \| claude \| copilot \| openai) |
| `DEVOPS_CLI_AI_RAG_ENABLED` | `ai.rag.enabled` | No | Retrieve related code and documents from the Qdrant index for AI tasks |
| `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD` | `ai.rag.score_threshold` | No | Lowest score, from 0 to 1, of a result that a RAG retrieval keeps |
| `DEVOPS_CLI_AI_RAG_TOP_K` | `ai.rag.top_k` | No | Number of results that a RAG retrieval returns |
| `DEVOPS_CLI_AI_REASONING_EFFORT` | `ai.reasoning_effort` | No | AI reasoning effort level (low \| medium \| high) |
| `DEVOPS_CLI_AI_REFERENCE_EMBEDDING_MODEL` | `ai.reference_embedding_model` | No | Hosted embedding model whose genai-prices price values the local embedding tokens in the AI spend reports |
| `DEVOPS_CLI_AI_REFERENCE_MODEL` | `ai.reference_model` | No | Hosted chat model whose genai-prices price values the local chat tokens in the AI spend reports |
| `DEVOPS_CLI_AI_REFERENCE_PROVIDER` | `ai.reference_provider` | No | Provider in genai-prices of the two reference models |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL` | `ai.tasks.analysis.model` | No | AI model of this task, in place of `ai.model` |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_OLLAMA_URLS` | `ai.tasks.analysis.ollama_urls` | No | Ollama service URLs of this task, in place of `ai.ollama_urls` |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER` | `ai.tasks.analysis.provider` | No | AI provider of this task, in place of `ai.provider` |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_REASONING_EFFORT` | `ai.tasks.analysis.reasoning_effort` | No | Reasoning effort of this task, in place of `ai.reasoning_effort` |
| `DEVOPS_CLI_AI_TASK_CHAT_MODEL` | `ai.tasks.chat.model` | No | AI model of this task, in place of `ai.model` |
| `DEVOPS_CLI_AI_TASK_CHAT_OLLAMA_URLS` | `ai.tasks.chat.ollama_urls` | No | Ollama service URLs of this task, in place of `ai.ollama_urls` |
| `DEVOPS_CLI_AI_TASK_CHAT_PROVIDER` | `ai.tasks.chat.provider` | No | AI provider of this task, in place of `ai.provider` |
| `DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT` | `ai.tasks.chat.reasoning_effort` | No | Reasoning effort of this task, in place of `ai.reasoning_effort` |
| `DEVOPS_CLI_AI_TASK_EMBEDDING_MODEL` | `ai.tasks.embedding.model` | No | AI model of this task, in place of `ai.model` |
| `DEVOPS_CLI_AI_TASK_EMBEDDING_OLLAMA_URLS` | `ai.tasks.embedding.ollama_urls` | No | Ollama service URLs of this task, in place of `ai.ollama_urls` |
| `DEVOPS_CLI_AI_TASK_EMBEDDING_PROVIDER` | `ai.tasks.embedding.provider` | No | AI provider of this task, in place of `ai.provider` |
| `DEVOPS_CLI_AI_TASK_EMBEDDING_REASONING_EFFORT` | `ai.tasks.embedding.reasoning_effort` | No | Reasoning effort of this task, in place of `ai.reasoning_effort` |
| `DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT` | `ai.tasks.embedding.timeout` | No | Seconds this task's requests wait for the next data of their reply, in place of `ai.timeout` |
| `DEVOPS_CLI_AI_TASK_METADATA_MODEL` | `ai.tasks.metadata.model` | No | AI model of this task, in place of `ai.model` |
| `DEVOPS_CLI_AI_TASK_METADATA_OLLAMA_URLS` | `ai.tasks.metadata.ollama_urls` | No | Ollama service URLs of this task, in place of `ai.ollama_urls` |
| `DEVOPS_CLI_AI_TASK_METADATA_PROVIDER` | `ai.tasks.metadata.provider` | No | AI provider of this task, in place of `ai.provider` |
| `DEVOPS_CLI_AI_TASK_METADATA_REASONING_EFFORT` | `ai.tasks.metadata.reasoning_effort` | No | Reasoning effort of this task, in place of `ai.reasoning_effort` |
| `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` | `argocd.github_app_id` | No | ID of the GitHub App that Argo CD's GitHub notifier acts as |
| `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` | `argocd.github_app_installation_id` | No | ID of the installation of Argo CD's notifier App on the managed repositories |
| `DEVOPS_CLI_ARGOCD_GITHUB_APP_PRIVATE_KEY` | `argocd.github_app_private_key` | 🔒 Yes | PEM private key of the GitHub App that Argo CD's GitHub notifier acts as (stored in OS keyring) |
| `DEVOPS_CLI_ARGOCD_PASSWORD` | `argocd.password` | 🔒 Yes | ArgoCD admin password (stored in OS keyring) |
| `DEVOPS_CLI_ARGOCD_TOKEN` | `argocd.token` | 🔒 Yes | ArgoCD API token (stored in OS keyring) |
| `DEVOPS_CLI_ARGOCD_URL` | `argocd.url` | No | ArgoCD service URL |
| `DEVOPS_CLI_CI_GATE_SLOTS` | `ci.gate_slots` | No | Number of CPU-heavy devops ci gates that run at once on this host (default: one for each 16 CPUs) |
| `DEVOPS_CLI_CLOUDFLARE_ACCESS_ALLOWED_EMAILS` | `cloudflare.access.allowed_emails` | No | List of email addresses permitted to authenticate through Cloudflare Access |
| `DEVOPS_CLI_CLOUDFLARE_ACCESS_BYPASS_IPS` | `cloudflare.access.bypass_ips` | No | List of public IP addresses or CIDR blocks permitted to bypass Cloudflare Access authentication |
| `DEVOPS_CLI_CLOUDFLARE_ACCESS_PUBLIC_IP_BYPASS` | `cloudflare.access.public_ip_bypass` | No | Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication |
| `DEVOPS_CLI_CLOUDFLARE_ACCOUNT_ID` | `cloudflare.account_id` | No | Cloudflare Account ID |
| `DEVOPS_CLI_CLOUDFLARE_API_TOKEN` | `cloudflare.api_token` | 🔒 Yes | Cloudflare API Token (stored in OS keyring) Also read from `CLOUDFLARE_API_TOKEN`. |
| `DEVOPS_CLI_CLOUDFLARE_DOMAIN` | `cloudflare.domain` | No | Root or zone domain name managed in Cloudflare (e.g. example.com) |
| `DEVOPS_CLI_CLOUDFLARE_PUBLIC_IP_BYPASS` | `cloudflare.public_ip_bypass` | No | Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication |
| `DEVOPS_CLI_CLOUDFLARE_TUNNEL` | `cloudflare.tunnel` | No | Cloudflare tunnel name or identifier (e.g. homelab) |
| `DEVOPS_CLI_CLOUDFLARE_TUNNEL_TOKEN` | `cloudflare.tunnel_token` | 🔒 Yes | Cloudflare Tunnel token that `devops k8s push-secrets` writes to the cluster (stored in OS keyring) |
| `DEVOPS_CLI_CLOUDFLARE_ZONE_ID` | `cloudflare.zone_id` | No | Cloudflare Zone ID |
| `DEVOPS_CLI_CONFIG` | *None* | No | Absolute path to project configuration file; outside devops-cli's own repository, the only one a `devops review` command reads |
| `DEVOPS_CLI_DATA_ANALYSIS_DIR` | `data.analysis_dir` | No | Storage directory for pre-analysis metadata JSON files |
| `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | `data.audit_log_path` | No | Path to structured audit JSONL log file |
| `DEVOPS_CLI_DATA_BENCHMARKS_DIR` | `data.benchmarks_dir` | No | Storage directory for benchmark test runs and embedding leaderboard reports |
| `DEVOPS_CLI_DATA_CACHE_DIR` | `data.cache_dir` | No | Storage directory for local response and retrieval cache |
| `DEVOPS_CLI_DATA_DIR` | `data.dir` | No | Root data directory for local reviews, cache, logs, and artifacts (default: ./.data; outside devops-cli's own repository, ~/.local/share/devops-cli/.data for review data and a `devops review` command) |
| `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | `data.feedback_dataset_path` | No | Path to feedback fine-tuning dataset JSONL file |
| `DEVOPS_CLI_DATA_LOGS_DIR` | `data.logs_dir` | No | Storage directory for CLI execution and SIEM audit logs |
| `DEVOPS_CLI_DATA_MODELS_DIR` | `data.models_dir` | No | Storage directory for local model checkpoints and weights |
| `DEVOPS_CLI_DATA_RAG_DIR` | `data.rag_dir` | No | Storage directory for local vector embedding index cache and retrieval data |
| `DEVOPS_CLI_DATA_REVIEWS_DIR` | `data.reviews_dir` | No | Storage directory for review session finding reports and artifacts |
| `DEVOPS_CLI_DATA_RUNS_DIR` | `data.runs_dir` | No | Storage directory for benchmark and evaluation run records, the run store's source of truth |
| `DEVOPS_CLI_DATA_SAMPLES_DIR` | `data.samples_dir` | No | Storage directory for open-source sample repositories fetched at their pinned commits |
| `DEVOPS_CLI_DATA_TLS_DIR` | `data.tls_dir` | No | Storage directory for generated local CA and TLS certificates |
| `DEVOPS_CLI_FIRECRAWL_API_KEY` | `firecrawl.api_key` | 🔒 Yes | API key for the Firecrawl web search API Also read from `FIRECRAWL_API_KEY`. |
| `DEVOPS_CLI_GITEA_ADMIN_PASSWORD` | `gitea.admin_password` | 🔒 Yes | Password of Gitea's admin user, which `devops k8s push-secrets` writes to Secret gitea/gitea-admin (stored in OS keyring) |
| `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | `github.default_org` | No | Default GitHub organization |
| `DEVOPS_CLI_GRAFANA_PASSWORD` | `grafana.password` | 🔒 Yes | Grafana admin password (stored in OS keyring) |
| `DEVOPS_CLI_GRAFANA_TOKEN` | `grafana.token` | 🔒 Yes | Grafana API token (stored in OS keyring) |
| `DEVOPS_CLI_GRAFANA_URL` | `grafana.url` | No | Grafana service URL |
| `DEVOPS_CLI_K8S_CONTEXT` | `k8s.context` | No | Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context) |
| `DEVOPS_CLI_K8S_DOMAIN` | `k8s.domain` | No | Base domain name for homelab ingress routes and tunnel services (e.g. example.com) |
| `DEVOPS_CLI_K8S_TUNNEL_HOST` | `k8s.tunnel_host` | No | Hostname of the Kubernetes API route through the Cloudflare tunnel, which 'devops k8s tunnel start' forwards to a local port (e.g. k8s.example.com) |
| `DEVOPS_CLI_MATTERMOST_ALERTS_HOOK` | `mattermost.alerts_hook` | 🔒 Yes | Mattermost incoming webhook token for the alerts channel (stored in OS keyring) |
| `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` | `mattermost.command_token` | 🔒 Yes | Mattermost slash command token for the /roadmap command (stored in OS keyring) |
| `DEVOPS_CLI_MATTERMOST_DEPLOYS_HOOK` | `mattermost.deploys_hook` | 🔒 Yes | Mattermost incoming webhook token for the deploys channel (stored in OS keyring) |
| `DEVOPS_CLI_PROMETHEUS_URL` | `prometheus.url` | No | Prometheus service URL |
| `DEVOPS_CLI_QDRANT_API_KEY` | `qdrant.api_key` | 🔒 Yes | Qdrant API key (stored in OS keyring) |
| `DEVOPS_CLI_QDRANT_COLLECTION_PREFIX` | `qdrant.collection_prefix` | No | Prefix for Qdrant collection names |
| `DEVOPS_CLI_QDRANT_TIMEOUT` | `qdrant.timeout` | No | Seconds each Qdrant request waits per attempt: RAG searches, and indexing's upserts and deletes, which share the client |
| `DEVOPS_CLI_QDRANT_URL` | `qdrant.url` | No | Qdrant vector database server URL |
| `DEVOPS_CLI_REPOS_BASE_DIR` | `repos.base_dir` | No | Base directory for cloned repositories |
| `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` | `roadmap.implement.in_runner` | No | Whether this process is the pod of a runner Job. Only then does `devops roadmap implement --confirm` run a step. The step's shell is no security boundary: the runner is the sandbox, with a narrow token and no other credential. The Service pod and a workstation keep this false |
| `DEVOPS_CLI_ROADMAP_IMPLEMENT_REPAIR_ROUNDS` | `roadmap.implement.repair_rounds` | No | The most extra turns that one implementation step gives the agent after its first run: one for each failed `ruff`, `mypy` or hook of the project, and one for each time that tasks stay unticked. The same number bounds the fix steps that the scoped checks before a push cause. When no round is left, the step or the item stops. 0 gives the agent no extra turn |
| `DEVOPS_CLI_ROADMAP_STAGE_FILTER` | `roadmap.stage.filter` | No | The labels of the items that the stage job takes, as entries `family=value` over the families status, priority, type, value and effort: the values of one family are alternatives, and the families all apply; the job also takes Ready items only |
| `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` | `roadmap.stage.limit` | No | The most items that one run of the stage job takes |
| `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS` | `roadmap.stage.step_tokens` | No | The most tokens that the inputs of one implementation step may hold: the step's instructions, the item, the change folder and the packed files of one task group; `devops roadmap stage` splits a task group over it |
| `DEVOPS_CLI_RUNS_INDEX_PASSWORD` | `runs.index_password` | 🔒 Yes | Run index Valkey password (stored in OS keyring) |
| `DEVOPS_CLI_RUNS_INDEX_URL` | `runs.index_url` | No | Valkey holding the run index shared by workstations (set by `devops ai runs connect`) |
| `DEVOPS_CLI_SANDBOX_EXCLUDE_HOME_DIR` | `sandbox.exclude_home_dir` | No | Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*) |
| `DEVOPS_CLI_SERVICE_DRAIN_TIMEOUT_SECONDS` | `service.drain_timeout_seconds` | No | Shutdown drain timeout for running service jobs in seconds |
| `DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID` | `service.github_app.app_id` | No | ID of the GitHub App that the roadmap Service and the cluster jobs act as |
| `DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID` | `service.github_app.installation_id` | No | ID of the App's installation on the account that owns the managed repositories |
| `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` | `service.github_app.private_key` | 🔒 Yes | PEM private key of the GitHub App (stored in OS keyring). A process whose environment holds it acts as the App |
| `DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG` | `service.github_app.slug` | No | Slug of the GitHub App; its bot's login is `<slug>[bot]` |
| `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` | `service.github_app.token_repository` | No | owner/name of the one repository that an installation token may name. Set on a runner Job by the Service, so a step cannot push to another repository. With it unset, a token covers every repository of the installation |
| `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | `service.github_requests_per_hour` | No | The most GitHub requests the Service sends in one hour; a request that the last hour has no room for waits. The alert RoadmapServiceGitHubRequestsHigh follows this limit |
| `DEVOPS_CLI_SERVICE_MODEL_CALL_CONCURRENCY` | `service.model_call_concurrency` | No | The most model calls the Service keeps in flight at once; a lane that waits does so in the Service, where no stall timer runs |
| `DEVOPS_CLI_SERVICE_POLL_INTERVAL_SECONDS` | `service.poll_interval_seconds` | No | Periodic polling interval for service mode in seconds |
| `DEVOPS_CLI_SERVICE_REPOS` | `service.repos` | No | Target repository list for service mode |
| `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | `service.webhook_secrets` | 🔒 Yes | JSON map of repo to webhook HMAC secret for incoming GitHub webhooks |
| `DEVOPS_CLI_SSH_KEY_DIR` | `ssh.key_dir` | No | Directory for SSH key pairs |
| `DEVOPS_CLI_SSH_KEY_PREFIX` | `ssh.key_prefix` | No | Prefix for generated SSH keys (defaults to devcontainer name or basename pwd) |
| `DEVOPS_CLI_SSH_ROTATION_DAYS` | `ssh.rotation_days` | No | SSH key rotation interval in days |
| `DEVOPS_CLI_TELEMETRY_CAPTURE_LLM_CONTENT` | `telemetry.capture_llm_content` | No | Record LLM prompt and reply text in OpenTelemetry and Logfire telemetry spans. Off by default to prevent exposure of sensitive data |
| `DEVOPS_CLI_TELEMETRY_ENABLED` | `telemetry.enabled` | No | Export OpenTelemetry traces and metrics |
| `DEVOPS_CLI_TELEMETRY_ENDPOINT` | `telemetry.endpoint` | No | OpenTelemetry collector that traces and metrics go to; unset, `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318` |
| `DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN` | `telemetry.logfire_token` | 🔒 Yes | Logfire write token (stored in OS keyring) Also read from `LOGFIRE_TOKEN`. |
| `DEVOPS_CLI_VALKEY_PASSWORD` | `valkey.password` | 🔒 Yes | Valkey authentication password (stored in OS keyring) |
| `DEVOPS_CLI_VALKEY_TIMEOUT` | `valkey.timeout` | No | Valkey network socket connection/read timeout in seconds; the shared cache of embeddings, threat intel and library symbols waits at most 0.25 s for a connection (default: 2.0) |
| `DEVOPS_CLI_VALKEY_URL` | `valkey.url` | No | The Valkey endpoint, such as `valkeys://example.com:6380/0`: the scheme, the host, the port and the database. The scheme `valkeys` connects over TLS and checks the certificate against the host. The scheme `valkey` connects in plaintext. The URL holds no password: `valkey.password` is in the OS keyring |
| `DEVOPS_CLI_WORKSPACE_FILE` | `workspace.file` | No | Path to VS Code workspace file |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *None* | No | OpenTelemetry's standard collector variable, read only when `telemetry.endpoint` is unset (default: http://localhost:4318) |

## Usage Notes

- A credential (`*.token`, `*.api_key`, `*.password`) goes to the OS keyring with `devops config set <key>`, which asks for it at a hidden prompt. A multi-line credential, such as a PEM private key, comes from a file with `devops config set <key> --from-file key.pem`, or from stdin with `--from-file -`.
- Environment variable overrides take precedence over values in `config.yaml`.
- Run `devops config output` to inspect all active environment variables.
