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
| **`ai`** | `AISettings` | LLM provider, models, tasks, caching, Ollama endpoints | `provider`, `model`, `ollama_urls`, `temperature`, `allow_private_network` |
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

## 3. Dotted Setting Access CLI Commands

```bash
# View active configuration summary
devops config show

# View configuration as raw JSON
devops config output --json

# Set configuration values using dotted notation
devops config set ai.provider ollama
devops config set ai.model qwen2.5-coder:7b
devops config set github.default_org my-org

# Get specific configuration values
devops config get ai.provider
devops config get github.token

# Manage encrypted secrets via OS Keyring
devops config set github.token ghp_xxxx
devops config set ai.api_key sk-xxxx
```
