# DevOps CLI Configuration & Settings Guide

This document details the configuration management architecture, Pydantic settings hierarchy, environment variable resolution, and secure OS Keyring token storage in `devops-cli`.

---

## 1. Configuration Resolution Order

Settings are resolved in the following priority order (highest to lowest):
1. **CLI Flags & Arguments** (e.g. `--token`, `--model`, `--endpoint`, `--dry-run`)
2. **Environment Variables** (e.g. `DEVOPS_CLI_AI_API_KEY`, `GITHUB_TOKEN`, `OTEL_EXPORTER_OTLP_ENDPOINT`)
3. **Encrypted Secret Store** (OS Keyring via Python `keyring` library)
4. **Persistent JSON Config** (`~/.config/devops-cli/config.json`)
5. **Default Settings** (`devops_cli.config.defaults` and Pydantic field defaults)

---

## 2. Settings Schema & Hierarchy

Configuration is modeled with immutable and mutable Pydantic v2 schemas:

| Section | Model | Description | Primary Fields |
| :--- | :--- | :--- | :--- |
| **`ai`** | `AISettings` | LLM provider, models, tasks, caching, Ollama endpoints | `provider`, `model`, `reasoning_effort`, `ollama_urls`, `ollama_max_parallel`, `temperature`, `max_tokens`, `tasks` |
| **`github`** | `GitHubSettings` | GitHub API access, default org, user | `token`, `default_org`, `default_user` |
| **`k8s`** | `K8sSettings` | Kubernetes cluster context and namespaces | `context`, `namespace`, `k8s_dir` |
| **`ssh`** | `SSHSettings` | SSH key management, directory, key types | `key_dir`, `key_type`, `key_size` |
| **`tls`** | `TLSSettings` | X.509 TLS certificate generation defaults | `tls_dir`, `organization`, `country`, `validity_days` |
| **`telemetry`** | `TelemetrySettings` | OpenTelemetry and Jaeger trace export | `enabled`, `endpoint`, `service_name`, `sample_rate` |
| **`prometheus`** | `PrometheusSettings` | Prometheus server API URL and query timeouts | `url`, `timeout_seconds` |
| **`grafana`** | `GrafanaSettings` | Grafana dashboard server URL and API keys | `url`, `api_key` |
| **`argo`** | `ArgoSettings` | ArgoCD server endpoint, token, and insecure flag | `url`, `token`, `insecure` |
| **`qdrant`** | `QdrantSettings` | Qdrant vector database URL and collection names | `url`, `code_collection`, `docs_collection` |
| **`workspace`** | `WorkspaceSettings` | Multi-repo workspace paths and roots | `root_dir`, `code_workspace_file` |

---

## 3. Environment Variable Overrides

All configuration values can be overridden via `DEVOPS_CLI_*` environment variables:

| Environment Variable | Target Setting | Description / Example |
| :--- | :--- | :--- |
| `DEVOPS_CLI_CONFIG_PATH` | System | Path to persistent configuration file (`~/.config/devops-cli/config.yaml`) |
| `DEVOPS_CLI_DATA_DIR` | System | Base directory for data, sessions, reviews, and logs (use `./.data/agent` for isolated AI tasks) |
| `DEVOPS_CLI_DRY_RUN` | System | Enable global dry-run mode (`1`, `true`, `yes`) |
| `DEVOPS_CLI_LOG_LEVEL` | System | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DEVOPS_CLI_AI_PROVIDER` | `ai.provider` | AI provider backend (`ollama`, `openai`, `anthropic`, `deepseek`) |
| `DEVOPS_CLI_AI_MODEL` | `ai.model` | Active AI model (e.g. `qwen3.8:27b`, `qwen2.5-coder:14b`, `gpt-4o`) |
| `DEVOPS_CLI_AI_REASONING_EFFORT` | `ai.reasoning_effort` | Reasoning depth for reasoning models (`low`, `medium`, `high`) |
| `DEVOPS_CLI_AI_TEMPERATURE` | `ai.temperature` | Sampling temperature (`0.0` to `1.0`) |
| `DEVOPS_CLI_AI_MAX_TOKENS` | `ai.max_tokens` | Response token generation ceiling (e.g. `2048`, `4096`) |
| `DEVOPS_CLI_AI_OLLAMA_URLS` | `ai.ollama_urls` | Comma-separated list of Ollama host endpoints (e.g. `http://hog.lan:11434,http://127.0.0.1:11434`) |
| `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | `ai.ollama_max_parallel` | Maximum concurrent requests dispatched per Ollama endpoint |
| `GITHUB_TOKEN` | `github.token` | GitHub Personal Access Token for API and PR operations |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `telemetry.endpoint` | OTLP gRPC collector target (e.g. `http://localhost:4317`) |

---

## 4. Task-Specific AI Configuration Overrides

Fine-tune AI parameters per task in `config.yaml` to optimize latency and token spend:

```yaml
ai:
  provider: ollama
  model: qwen3.8:27b
  reasoning_effort: low
  temperature: 0.1
  max_tokens: 4096
  tasks:
    review:
      temperature: 0.1
      max_tokens: 2048
      reasoning_effort: low
      timeout_seconds: 240
    embedding:
      ollama_urls:
        - http://workhorse.lan:11434
      model: qwen3-embedding:0.6b
    chat:
      temperature: 0.7
      max_tokens: 4096
    diagram:
      temperature: 0.2
      max_tokens: 2048
  rag:
    embedding_url: http://workhorse.lan:11434
    embedding_model: qwen3-embedding:0.6b
```

---

## 5. Dotted Setting Access CLI Commands

```bash
# View active configuration summary
devops config show

# View configuration as raw JSON
devops config output --json

# Set configuration values using dotted notation
devops config set ai.provider ollama
devops config set ai.model qwen3.8:27b
devops config set ai.reasoning_effort low
devops config set ai.allow_private_network true
devops config set ai.rag.embedding_url http://workhorse.lan:11434
devops config set ai.tasks.embedding.ollama_urls http://workhorse.lan:11434
devops config set github.default_org my-org

# Get specific configuration values
devops config get ai.provider
devops config get ai.rag.embedding_url
devops config get github.token

# Audit configuration for unencrypted plaintext credentials
devops config audit-keys

# Manage encrypted secrets via OS Keyring
devops config set github.token ghp_xxxx
devops config set ai.api_key sk-xxxx
```
