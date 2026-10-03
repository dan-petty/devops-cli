# DevOps CLI Configuration Reference

This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).

DevOps CLI supports hierarchical configuration resolution through:
1. **CLI Flags & Arguments** (highest precedence)
2. **Environment Variables** (`DEVOPS_CLI_*`)
3. **Local Project Configuration** (the file `DEVOPS_CLI_CONFIG` names, else the nearest `config.yaml`, `.devops/config.yaml` or `.devops.yaml` from the working directory up to its repository root)
4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)
5. **System Defaults**

A `devops review` command reads a tree it does not own. Started in a repository other than devops-cli's own, it looks for no project configuration, reading only the file `DEVOPS_CLI_CONFIG` names, and it resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. What a review keeps -- its sessions, the hallucination catalog, the mitigations ledger, the feedback dataset, runs, samples, library contracts and AI spend -- every other command started outside devops-cli's own repository reads and writes there too. devops-cli's own repository is the one whose checkout holds the source of the devops-cli that runs, as an editable install's does; its code already runs, so a review started there, or in any worktree of it, reads its project configuration and keeps all data under its main worktree's `.data`, as every other command does. A clone nested in that checkout is another repository, and an installed devops-cli trusts no repository this way. An absolute `DEVOPS_CLI_DATA_DIR` or `data.dir` names the data directory every command uses.

---

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

## Telemetry & Metrics (`telemetry`)

OpenTelemetry distributed tracing and Prometheus metric export settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `enabled` | `bool` | `True` | `DEVOPS_CLI_TELEMETRY_ENABLED` | Export OpenTelemetry traces and metrics |
| `endpoint` | `Union` | - | `DEVOPS_CLI_TELEMETRY_ENDPOINT` | OpenTelemetry collector that traces and metrics go to; unset, `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318` |
| `logfire` | `bool` | `False` | - | - |
| `logfire_token` | `Union` | - | - | - |
| `logfire_send_to_logfire` | `Union` | `if-token-present` | - | - |

## Kubernetes Configuration (`k8s`)

Kubernetes cluster connection, Minikube, Helm, and Kustomize settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `context` | `str` | `minikube` | `DEVOPS_CLI_K8S_CONTEXT` | Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context) |
| `domain` | `Union` | - | `DEVOPS_CLI_K8S_DOMAIN` | Base domain name for homelab ingress routes and tunnel services (e.g. retric.ai) |
| `addressing` | `Union` | - | - | Default addressing mode for cluster services: nodeport, proxy, or fqdn. |

## AI & LLM Configuration (`ai`)

AI code review, multi-agent pipelines, RAG semantic search, and embeddings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `provider` | `str` | `ollama` | `DEVOPS_CLI_AI_PROVIDER` | - |
| `model` | `str` | `gemma4:26b` | `DEVOPS_CLI_AI_MODEL` | - |
| `reference_model` | `str` | `gpt-4o` | - | - |
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
| `vllm_url` | `str` | `http://localhost:8000/v1` | - | - |
| `api_base_url` | `Union` | - | `DEVOPS_CLI_AI_API_BASE_URL` | - |
| `allow_private_network` | `bool` | `False` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | - |
| `max_retries` | `int` | `4` | `DEVOPS_CLI_AI_MAX_RETRIES` | - |
| `timeout` | `Union` | - | - | - |
| `tasks` | `AITasksConfig` | `chat=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) metadata=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) analysis=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) verification=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) compose=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) embedding=AITaskOverride(provider=None, model='qwen3-embedding:0.6b', reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None)` | - | - |
| `rag` | `AIRAGConfig` | `enabled=True top_k=5 score_threshold=0.35 chunk_size=2400 chunk_overlap=240` | - | - |
| `cache` | `AICacheConfig` | `enabled=True backend='file' dir=PosixPath('.data/cache/llm') ttl_seconds=604800 max_entries=1000 append_cache=False` | - | - |
| `durable` | `AIDurableConfig` | `engine='sqlite' store_path=PosixPath('.data/durable_runs.db') task_queue='devops-cli-tasks' workflow_id_prefix='devops-run-'` | - | - |
| `task_name` | `Union` | - | - | - |

## Qdrant Vector Store (`qdrant`)

The vector store that RAG searches query and indexing writes to.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `http://localhost:6333` | `DEVOPS_CLI_QDRANT_URL` | - |
| `collection_prefix` | `str` | `devops` | `DEVOPS_CLI_QDRANT_COLLECTION_PREFIX` | - |
| `api_key` | `Union` | - | `DEVOPS_CLI_QDRANT_API_KEY` | - |
| `timeout` | `float` | `300.0` | `DEVOPS_CLI_QDRANT_TIMEOUT` | Seconds each Qdrant request waits per attempt: RAG searches, and indexing's upserts and deletes, which share the client |

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
