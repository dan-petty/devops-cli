# DevOps CLI Configuration & Settings Guide

This document details the configuration management architecture, Pydantic settings hierarchy, environment variable resolution, and secure OS Keyring token storage in `devops-cli`.

---

## 1. Configuration Resolution Order

Settings are resolved in the following priority order (highest to lowest):

**Secrets:**
1. **OS Keyring** (via Python `keyring` library)
2. **Vault** (via HashiCorp Vault broker)
3. **Environment Variables** (e.g. `DEVOPS_CLI_AI_API_KEY`)
4. **Configuration File** (`config.yaml`)

**Other Settings:**
1. **CLI Flags & Arguments** (e.g. `--model`, `--endpoint`, `--dry-run`)
2. **Environment Variables** (`DEVOPS_CLI_*` overrides)
3. **Project Config File** (`./config.yaml`)
4. **Global User Config File** (`~/.config/devops-cli/config.yaml`)
5. **Default Settings** (`devops_cli.config.defaults` and Pydantic field defaults)

A config file that is not valid YAML stops the settings from loading. The error names the file, the type of the YAML error, and the line and the column where the parser stopped, such as `Cannot load the settings: <file> is not valid YAML (ScannerError) at line 2, column 22.` The error quotes no text of the file, because that line can hold a credential. A file that is not UTF-8, or a tagged value that PyYAML cannot build, such as `!!int <text>`, gives the same error with no line and no column, such as `(ValueError).`

---

## 2. Settings Schema & Hierarchy

Configuration is modeled with immutable and mutable Pydantic v2 schemas:

| Section | Model | Description | Primary Fields |
| :--- | :--- | :--- | :--- |
| **`ai`** | `AIConfig` | LLM provider, models, tasks, caching, Ollama endpoints | `provider`, `model`, `reasoning_effort`, `temperature`, `max_tokens`, `ollama_urls`, `ollama_max_parallel`, `tasks`, `rag`, `cache` |
| **`github`** | `GitHubConfig` | Default organization (the token is gh's login, from `gh auth token`) | `default_org` |
| **`k8s`** | `KubernetesConfig` | Kubernetes cluster context and domain configuration | `context`, `domain`, `addressing` |
| **`ssh`** | `SSHConfig` | SSH key management, directory, key prefix, rotation | `key_dir`, `key_prefix`, `rotation_days` |
| **`telemetry`** | `TelemetryConfig` | OpenTelemetry and Logfire export | `enabled`, `endpoint`, `logfire` |
| **`prometheus`** | `PrometheusConfig` | Prometheus server API URL | `url` |
| **`grafana`** | `GrafanaConfig` | Grafana dashboard server URL | `url` |
| **`argocd`** | `ArgoCDConfig` | ArgoCD server endpoint URL | `url` |
| **`qdrant`** | `QdrantConfig` | Qdrant vector database URL and collection settings | `url`, `collection_prefix`, `timeout` |
| **`workspace`** | `WorkspaceConfig` | Multi-repo `.code-workspace` manifest file path | `file` |
| **`repos`** | `ReposConfig` | Base directory for multi-repository management | `base_dir` |

---

## 3. Environment Variable Overrides

The configuration keys listed in docs/ENV_VARS.md can be overridden via `DEVOPS_CLI_*` environment variables:

| Environment Variable | Target Setting | Description / Example |
| :--- | :--- | :--- |
| `DEVOPS_CLI_CONFIG` | System | Absolute path to the configuration file to use instead of the project/global lookup (global default `~/.config/devops-cli/config.yaml`) |
| `DEVOPS_CLI_DATA_DIR` | System | Base workspace directory for data, sessions, reviews, and logs (defaults to `./.data`; agent artifacts isolate under `<data_dir>/agent`) |
| `DEVOPS_CLI_DRY_RUN` | System | Enable global dry-run mode (`1`, `true`, `yes`) |
| `DEVOPS_CLI_AI_PROVIDER` | `ai.provider` | AI provider backend (`ollama`, `claude`, `copilot`, `openai`, `gateway`) |
| `DEVOPS_CLI_AI_MODEL` | `ai.model` | Active AI model (e.g. `qwen3.8:27b`, `qwen2.5-coder:14b`, `gpt-4o`) |
| `DEVOPS_CLI_AI_REASONING_EFFORT` | `ai.reasoning_effort` | Reasoning depth for reasoning models (`low`, `medium`, `high`) |
| `DEVOPS_CLI_AI_OLLAMA_URLS` | `ai.ollama_urls` | Comma-separated list of Ollama host endpoints (e.g. `http://192.0.2.10:11434,http://127.0.0.1:11434`) |
| `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | `ai.ollama_max_parallel` | Maximum concurrent requests dispatched per Ollama endpoint |
| `DEVOPS_CLI_TELEMETRY_ENABLED` | `telemetry.enabled` | Export OpenTelemetry traces and metrics (`true`, `false`) |
| `DEVOPS_CLI_TELEMETRY_ENDPOINT` | `telemetry.endpoint` | OpenTelemetry collector endpoint |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `telemetry.endpoint`, when unset | OpenTelemetry's standard variable, read only when no configuration names `telemetry.endpoint` |

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
    analysis:
      temperature: 0.1
      max_tokens: 2048
      reasoning_effort: low
      timeout: 240
    verification:
      temperature: 0.1
      max_tokens: 2048
      timeout: 240
    embedding:
      ollama_urls:
        - http://192.0.2.10:11434
      model: qwen3-embedding:0.6b
    chat:
      temperature: 0.7
      max_tokens: 4096
  rag:
    enabled: true
    top_k: 5
    score_threshold: 0.35
```

### Sampling and Context Settings

AI providers handle sampling and context parameters differently:

- **`num_ctx`**: Valid only when `provider` is `ollama`. Native Ollama passes `num_ctx` in request options. Providers using OpenAI APIs (`gateway`, `openai`, `copilot`) reject `num_ctx` with a configuration error. Configure the context size on the gateway backend or server deployment instead.
- **`use_model_sampling`**: Boolean flag (`false` by default) set at root `ai` or per task under `ai.tasks.<task>`. When set to `true`, the client omits `temperature` and `top_p` from requests, so the model deployment uses its configured defaults.
- **Serving and Tag Parameters**: Settings such as `top_k`, `repeat_penalty`, `presence_penalty`, `min_p`, `think`, and `keep_alive` are forbidden in `ai` and `ai.tasks.<task>`. Configure these parameters in the gateway deployment `litellm_params` or in the Ollama Modelfile.
- **Unknown keys**: `ai`, `ai.tasks` and each `ai.tasks.<task>` refuse a key that they do not declare. Such a key stops the settings from loading. The error names the full dotted key, its file and line, the release that removed the key when devops-cli knows it, and the command that removes it, such as `devops config unset ai.vllm_url`.

---

## 5. Dotted Setting Access CLI Commands

```bash
# View active configuration summary
devops config show

# List configuration environment variables
devops config output --json

# Set configuration values using dotted notation
devops config set ai.provider ollama
devops config set ai.model qwen3.8:27b
devops config set ai.reasoning_effort low
devops config set ai.allow_private_network true
devops config set ai.tasks.embedding.ollama_urls http://192.0.2.10:11434
devops config set github.default_org my-org

# Remove a key from the config file, also a key that stops the settings from loading
devops config unset ai.vllm_url

# Get specific configuration values
devops config get ai.provider
devops config get ai.tasks.embedding.ollama_urls
devops config get github.default_org

# Audit configuration for unencrypted plaintext credentials
devops config audit-keys

# Remove a plaintext credential from the file that the audit names: store it in the keyring
# first, with --from-file <path> for a multi-line one. The .bak copies of the file show the
# removed value as ***REDACTED***
devops config set <key>
DEVOPS_CLI_CONFIG=<file> devops config unset <key>

# Store a credential in the OS keyring; omit the value to type it at a hidden prompt
devops config set ai.api_key

# Read a multi-line credential, such as a PEM private key, from a file (`-` reads stdin)
devops config set <key> --from-file key.pem

# GitHub access is gh's login: one identity per process, from `gh auth token`
gh auth login
```
