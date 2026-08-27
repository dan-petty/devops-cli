# Configuration Environment Variables

All configuration options for `devops-cli` can be overridden via environment variables or loaded from OS Keyring for sensitive secrets.

| Environment Variable | Config Key | Secret | Description |
|---|---|---|---|
| `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | `ai.allow_private_network` | No | Permit private-IP network targets |
| `DEVOPS_CLI_AI_API_BASE_URL` | `ai.api_base_url` | No | AI API base URL |
| `DEVOPS_CLI_AI_API_KEY` | `ai.api_key` | 🔒 Yes | AI API key (stored in OS keyring) |
| `DEVOPS_CLI_AI_MAX_RETRIES` | `ai.max_retries` | No | Maximum retry count for AI requests upon response validation failure |
| `DEVOPS_CLI_AI_MODEL` | `ai.model` | No | Default AI model name |
| `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | `ai.ollama_max_parallel` | No | Maximum parallel requests per Ollama host |
| `DEVOPS_CLI_AI_OLLAMA_URLS` | `ai.ollama_urls` | No | Ollama service URLs (comma-separated) |
| `DEVOPS_CLI_AI_PROVIDER` | `ai.provider` | No | AI provider (ollama \| claude \| copilot \| openai) |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL` | `ai.tasks.analysis.model` | No | AI model override for analysis task |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_OLLAMA_URLS` | `ai.tasks.analysis.ollama_urls` | No | Ollama URLs override for analysis task |
| `DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER` | `ai.tasks.analysis.provider` | No | AI provider override for analysis task |
| `DEVOPS_CLI_AI_TASK_CHAT_MODEL` | `ai.tasks.chat.model` | No | AI model override for chat task |
| `DEVOPS_CLI_AI_TASK_CHAT_OLLAMA_URLS` | `ai.tasks.chat.ollama_urls` | No | Ollama URLs override for chat task |
| `DEVOPS_CLI_AI_TASK_CHAT_PROVIDER` | `ai.tasks.chat.provider` | No | AI provider override for chat task |
| `DEVOPS_CLI_AI_TASK_COMPOSE_MODEL` | `ai.tasks.compose.model` | No | AI model override for compose task |
| `DEVOPS_CLI_AI_TASK_COMPOSE_OLLAMA_URLS` | `ai.tasks.compose.ollama_urls` | No | Ollama URLs override for compose task |
| `DEVOPS_CLI_AI_TASK_COMPOSE_PROVIDER` | `ai.tasks.compose.provider` | No | AI provider override for compose task |
| `DEVOPS_CLI_AI_TASK_METADATA_MODEL` | `ai.tasks.metadata.model` | No | AI model override for metadata task |
| `DEVOPS_CLI_AI_TASK_METADATA_OLLAMA_URLS` | `ai.tasks.metadata.ollama_urls` | No | Ollama URLs override for metadata task |
| `DEVOPS_CLI_AI_TASK_METADATA_PROVIDER` | `ai.tasks.metadata.provider` | No | AI provider override for metadata task |
| `DEVOPS_CLI_ARGOCD_TOKEN` | `argocd.token` | 🔒 Yes | ArgoCD API token (stored in OS keyring) |
| `DEVOPS_CLI_ARGOCD_URL` | `argocd.url` | No | ArgoCD service URL |
| `DEVOPS_CLI_CONFIG` | *None* | No | Absolute path to project configuration file |
| `DEVOPS_CLI_DATA_ANALYSIS_DIR` | `data.analysis_dir` | No | Storage directory for pre-analysis metadata JSON files |
| `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | `data.audit_log_path` | No | Path to structured audit JSONL log file |
| `DEVOPS_CLI_DATA_BENCHMARKS_DIR` | `data.benchmarks_dir` | No | Storage directory for benchmark test runs and embedding leaderboard reports |
| `DEVOPS_CLI_DATA_CACHE_DIR` | `data.cache_dir` | No | Storage directory for local response and retrieval cache |
| `DEVOPS_CLI_DATA_DIR` | `data.dir` | No | Root data directory for local reviews, cache, logs, and artifacts (default: ./.data) |
| `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | `data.feedback_dataset_path` | No | Path to feedback fine-tuning dataset JSONL file |
| `DEVOPS_CLI_DATA_LOGS_DIR` | `data.logs_dir` | No | Storage directory for CLI execution and SIEM audit logs |
| `DEVOPS_CLI_DATA_MODELS_DIR` | `data.models_dir` | No | Storage directory for local model checkpoints and weights |
| `DEVOPS_CLI_DATA_RAG_DIR` | `data.rag_dir` | No | Storage directory for local vector embedding index cache and retrieval data |
| `DEVOPS_CLI_DATA_REVIEWS_DIR` | `data.reviews_dir` | No | Storage directory for review session finding reports and artifacts |
| `DEVOPS_CLI_DATA_TLS_DIR` | `data.tls_dir` | No | Storage directory for generated local CA and TLS certificates |
| `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | `github.default_org` | No | Default GitHub organization |
| `DEVOPS_CLI_GITHUB_TOKEN` | `github.token` | 🔒 Yes | GitHub Personal Access Token (stored in OS keyring) |
| `DEVOPS_CLI_GRAFANA_TOKEN` | `grafana.token` | 🔒 Yes | Grafana API token (stored in OS keyring) |
| `DEVOPS_CLI_GRAFANA_URL` | `grafana.url` | No | Grafana service URL |
| `DEVOPS_CLI_PROMETHEUS_URL` | `prometheus.url` | No | Prometheus service URL |
| `DEVOPS_CLI_REPOS_BASE_DIR` | `repos.base_dir` | No | Base directory for cloned repositories |
| `DEVOPS_CLI_SSH_KEY_DIR` | `ssh.key_dir` | No | Directory for SSH key pairs |
| `DEVOPS_CLI_SSH_ROTATION_DAYS` | `ssh.rotation_days` | No | SSH key rotation interval in days |
| `DEVOPS_CLI_WORKSPACE_FILE` | `workspace.file` | No | Path to VS Code workspace file |

## Usage Notes

- Secret tokens (`*.token`, `*.api_key`) should be set via `devops config set <key> <val>` to store them securely in the OS Keyring.
- Environment variable overrides take precedence over values in `config.yaml`.
- Run `devops config output` to inspect all active environment variables.
