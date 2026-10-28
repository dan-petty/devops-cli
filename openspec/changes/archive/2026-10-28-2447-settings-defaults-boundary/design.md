# Design

## Decisions

### A value that a caller does not give is the loaded setting

A class that holds a setting (`SemanticChunker`, `SemanticRetriever`, `QdrantClient`, `ValkeyClient`, `LLMResponseCache`) reads the loaded settings when its caller passes no value. `QdrantClient` and `LLMResponseCache` already did so for their API key and cache directory. A caller that leaves a value out then gets the configured value, never a fixed one, and a caller that passes a value keeps it.

Rejected: make each value a required argument. Every production caller of `QdrantClient`, `ValkeyClient` and `LLMResponseCache` passes the setting, but 25 tests build a `QdrantClient` and 15 a `ValkeyClient` with no timeout, and `SemanticChunker` has no production caller that passes its sizes, which is how `ai.rag.chunk_size` came to be ignored. A required argument moves the setting into each caller; reading it in the class keeps it in one place.

Kept as required arguments: `acquire_ollama_slot`, `track_ollama_url` and `QdrantClient.search_points`. They run once for each request, where a load of the settings (about 4.4 ms, #1420) is a cost, and every caller passes the value.

### `setting_default` only where no settings are loaded

The fallback of a module whose settings cannot load reads the declared default by its dotted key. It keeps the behavior of the old fallback and names the field, not a copy.

### The GitHub cache root is read once for each process

`session_transport` resolves an identity's limiter twice for each request. A load of the settings in that path would add about 9 ms to each request. `_identity_cache_root` keeps `data.cache_dir` for the process, and `reset_github_rate_limiter`, which the test floor calls, reads it again.

### The audit check uses one data directory

The audit destination must be in `data.dir` of the loaded settings, resolved as the audit log is. Before, it accepted the default data directory of the working directory and `DEVOPS_CLI_DATA_DIR` both. The variable still sets `data.dir`, so a destination in it is still accepted; one in `.data` of the working directory is not, when the settings name another data directory.

### Group analysis records what the client sends

The client of the review's `analysis` task sends `ai.tasks.analysis`, else `ai`. `configured_sampling()` reads the same, so the record names the model's sampling. With `use_model_sampling` on, the client sends no temperature; the record still holds the configured values. Recording `null` there is the scope of the ai-model-sampling capability, not of this change.

### The invariant derives its names

The invariant reads the settings module's imports from `config/defaults.py` and the default expressions of its fields. Rejected:

- Ruff `banned-api`: a hand-kept list of 49 names that a new field would miss.
- Moving every field default into the settings module or a new module with one ban: three non-field defaults (`DEFAULT_SANDBOX_DATA_DIR`, `DEFAULT_RAG_CACHE_DIR`, `DEFAULT_BUNDLE_MODELS`) derive from field defaults in `config/defaults.py`, so the move would reach past this item, and a module ban needs a per-file exception for `config/` that also lifts the existing socket bans there.
