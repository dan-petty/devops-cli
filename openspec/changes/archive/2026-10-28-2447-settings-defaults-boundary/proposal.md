# Proposal

## Why

Issue #2447, part 3 of #1000: a `DEFAULT_*` value that is the default of a settings field was also imported by feature modules. A module that reads the default by its name does not see a config file or a variable that sets the setting. On origin/main d156ce7e, 23 such names were imported at 40 places in 27 modules outside `config/`.

Seven of these places ignored a setting that a user can set:

- `SemanticChunker`, and so the workspace indexer and the code-retrieval benchmark, split files by the default chunk size and overlap. No module read `ai.rag.chunk_size` or `ai.rag.chunk_overlap`.
- `devops ai rag search` gave `--top-k` and `--min-score` the defaults, so `ai.rag.top_k` and `ai.rag.score_threshold` did not apply.
- The `rag_search` tool of the agents gave the retriever no score threshold, and `top_k` defaulted to the default, so a model search used neither setting.
- Group analysis of a review recorded the defaults of `ai.temperature` and `ai.top_p` as its sampling. The client of the `analysis` task sends `ai.tasks.analysis`, so the report named values that the model did not get.
- The audit log accepted `DEVOPS_CLI_AUDIT_LOG_DEST` only in the default data directory, resolved from the working directory, or in `DEVOPS_CLI_DATA_DIR`. A `data.dir` of the config file did not count.
- The quota ledger and response cache of each GitHub identity were under `DEVOPS_CLI_DATA_DIR`, else under `.data/cache` of the working directory. `data.dir` and `data.cache_dir` of the config file did not apply.
- The roadmap Service kept its state under `DEVOPS_CLI_DATA_DIR`, else under `.data` of the working directory, and not under `data.dir` of the config file. The snapshot digest of the OSV database was kept under `.data/cache` of the working directory, not under `data.cache_dir`.

## What Changes

- `config/settings.py` gains `setting_default(key)`: the default that the settings field of a dotted key declares. A module reads it only where no settings are loaded, such as the fallback when the settings cannot load.
- Each of the 40 places reads the loaded setting, or `setting_default`, or names its own value:
  - A value that a caller does not give is the loaded setting: `SemanticChunker`, `WorkspaceIndexer`, `SemanticRetriever`, `QdrantClient` (`qdrant.timeout`), `ValkeyClient` (`valkey.timeout`) and `LLMResponseCache` (`data.cache_dir` and `ai.cache`). `get_llm_response_cache` gives its arguments to `LLMResponseCache` and resolves none itself.
  - `devops ai rag search` resolves `--top-k` and `--min-score` from `ai.rag` before its dry run, and the help names the settings. `rag_search` gives the retriever both settings.
  - `run_group_analysis` with no sampling records `configured_sampling()`: the `analysis` task's temperature and top-p of the loaded settings. `SamplingRecord` has no default temperature or top-p.
  - The audit check, the GitHub identity cache directory, the Service state directory and the OSV snapshot digest resolve `data.dir` or `data.cache_dir` of the loaded settings with `resolve_data_path`, as every other data path does. The GitHub cache root is read once for each process, so a request does not load the settings, and `reset_github_rate_limiter` reads it again.
  - `acquire_ollama_slot`, `track_ollama_url` and `QdrantClient.search_points` take `max_parallel` and `limit` from their callers, which pass the settings. The Ollama client reads `ai.ollama_max_parallel` from its config, and `get_context_window` reads `num_ctx` or `context_window`, with no fallback that cannot happen.
  - The fallbacks when the settings cannot load (`ci/cache.py`, `core/repo.py`, the two sandbox engines, the threat-intel cache, the spend ledger's reference models, the embedding model) read `setting_default`.
  - `devops k8s configure-urls` compares a saved Valkey URL with `setting_default("valkey.url")`.
  - The spend report's reference models have no default model: the ledger sets them, and `HardwarePayoffSummary` takes its reference model from its caller.
  - The AIBOM hardware estimate names its own context window, `_ESTIMATE_CONTEXT_WINDOW`. It is the window that the estimate of a model file assumes, not `ai.context_window`.
- `_resolve_llm_cache` in `ai/client/unified.py` loses its copies of the cache defaults (`86400 * 7`, `1000`), which a change to a default would leave behind.
- An invariant in `tests/invariants/test_source_tree.py` finds every read of a setting's default outside `config/`. It derives the names from the settings module, so a field added later is covered with no list to keep.
- `CONTRIBUTING.md` states the rule in the Constant row of the naming table.
- The results of the seven places above change, so the change carries a spec delta: ADDED requirements in `config-commands`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `config-commands`: a setting reaches each module that reads it, and a setting's default is read through the settings.

## Impact

- `src/devops_cli/config/settings.py`, and the 27 modules that imported a setting's default: in `ai/client/`, `ai/rag/`, `ai/spend/`, `ai/tools/`, `ai/response_cache.py`, `ci/`, `commands/`, `core/`, `docker/`, `github/`, `review/`, `roadmap/`, `sandbox/`, `security/` and `valkey/`.
- `src/devops_cli/lang/en/help.py`, and the generated `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/ai.md`.
- `CONTRIBUTING.md`.
- `tests/config/test_setting_overrides_reach_their_readers.py` (new), `tests/invariants/test_source_tree.py`, and the tests that used a removed default: `tests/test_ollama_dynamic_leasing.py`, `tests/test_audit_stream.py`, `tests/test_review_group_analysis.py`, `tests/test_rag_qdrant.py` and `tests/test_rag_embedding_model_compatibility.py`.

## Feasibility

- The importers were measured on origin/main d156ce7e with `ast`. A name is a setting's default when the settings module imports it from `config/defaults.py` and a field takes it as `Field(default=...)`, `Field(default_factory=...)`, the first argument of `Field`, or the assigned value. The issue's count, 26 names in 39 files, also took names that only a field's description reads. `DEFAULT_HTTP_TIMEOUT_SECONDS`, `DEFAULT_REVIEW_TIMEOUT_SECONDS` and `DEFAULT_OTEL_ENDPOINT` are such names: `ai.timeout` defaults to `None`. They are not in scope.
- The new invariant failed on the base with the 40 places. Each of the 8 tests in `tests/config/test_setting_overrides_reach_their_readers.py` failed on the base with the ignored value, for example `assert (2400, 240) == (900, 90)` for the chunker and `assert (0.1, 0.95) == (0.7, 0.8)` for group analysis.
- `LLMClient.chat` takes `temperature`, `top_p` and `seed` in `**kwargs` and does not use them; the payload reads the client's config. This is why the old sampling record named values that the model did not get. It is filed as #2559.
- The OSV snapshot digest hashes a directory under `data.cache_dir`, while osv-scanner keeps its database under `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY` or the user cache directory. #2130 owns the digest of the database; this change only stops the digest from ignoring `data.cache_dir`.

## Existing Tool Considered

- pydantic gives the declared default of a field (`FieldInfo.get_default`), which `setting_default` returns. Nothing new holds a default.
- Ruff's `banned-api` (TID251) bans names by a list in `pyproject.toml`. The list would hold 49 names by hand, and a field added later would not be on it. ast-grep matches the syntax of one file, and cannot tell which names a settings field takes as its default.
- The invariant uses Python's `ast` module, as the other invariants of `tests/invariants/test_source_tree.py` do (#1003, #2487). It derives its names, so it keeps no list and no baseline.
- The change deletes the per-module copies of the defaults and the duplicated cache defaults of `_resolve_llm_cache`. Written cost of the invariant: about 50 lines, built in under one hour, with no upkeep beyond the settings module it reads.
