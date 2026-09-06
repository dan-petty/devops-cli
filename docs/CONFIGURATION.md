# DevOps CLI Configuration Reference

This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).

DevOps CLI supports hierarchical configuration resolution through:
1. **CLI Flags & Arguments** (highest precedence)
2. **Environment Variables** (`DEVOPS_CLI_*`)
3. **Local Project Configuration** (`.devops-cli.yaml`)
4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)
5. **System Defaults**

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
| `enabled` | `bool` | `True` | - | - |
| `endpoint` | `str` | `http://localhost:4318` | - | - |

## AI & LLM Configuration (`ai`)

AI code review, multi-agent pipelines, RAG semantic search, and embeddings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `provider` | `str` | `ollama` | `DEVOPS_CLI_AI_PROVIDER` | - |
| `model` | `str` | `gemma4:26b` | `DEVOPS_CLI_AI_MODEL` | - |
| `reasoning_effort` | `Union` | - | `DEVOPS_CLI_AI_REASONING_EFFORT` | - |
| `temperature` | `float` | `0.1` | - | - |
| `top_p` | `float` | `0.95` | - | - |
| `context_window` | `int` | `32768` | - | - |
| `num_ctx` | `Union` | - | - | - |
| `max_tokens` | `Union` | - | - | - |
| `ollama_urls` | `list` | `['http://localhost:11434']` | `DEVOPS_CLI_AI_OLLAMA_URLS` | - |
| `ollama_max_parallel` | `int` | `2` | `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | - |
| `api_base_url` | `Union` | - | `DEVOPS_CLI_AI_API_BASE_URL` | - |
| `allow_private_network` | `bool` | `False` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | - |
| `max_retries` | `int` | `2` | `DEVOPS_CLI_AI_MAX_RETRIES` | - |
| `append_cache` | `bool` | `False` | - | - |
| `tasks` | `AITasksConfig` | `chat=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None) metadata=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None) analysis=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None) compose=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None) embedding=AITaskOverride(provider=None, model=None, reasoning_effort=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None)` | - | - |
| `rag` | `AIRAGConfig` | `enabled=True embedding_model='qwen3-embedding:0.6b' embedding_url=None top_k=5 score_threshold=0.35 chunk_size=2400 chunk_overlap=240` | - | - |
| `cache` | `AICacheConfig` | `enabled=True dir=PosixPath('.data/cache/llm') ttl_seconds=604800 max_entries=1000 append_cache=False` | - | - |
| `durable` | `AIDurableConfig` | `engine='sqlite' store_path=PosixPath('.data/durable_runs.db') task_queue='devops-cli-tasks' workflow_id_prefix='devops-run-'` | - | - |

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
| `tls_dir` | `Path` | `.data/tls` | `DEVOPS_CLI_DATA_TLS_DIR` | - |
| `audit_log_path` | `Path` | `.data/logs/audit.jsonl` | `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | - |
| `feedback_dataset_path` | `Path` | `.data/feedback_dataset.jsonl` | `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | - |
