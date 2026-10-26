# Proposal

## Why

Issue #1014: the response cache trusts the files in its directory and does not validate that loaded entries match requested keys.
An attacker can place malicious entries with directory traversal sequences in the key field or in the directory under review.
This can overwrite files outside the cache directory or serve attacker-controlled model responses without model calls.
Furthermore, empty responses and responses failing schema validation were improperly cached, while cache status and clear commands could resolve an inconsistent cache directory.

## What Changes

- The response cache reads and writes only files named `<cache_dir>/<requested_key>.json`.
- Cache keys must be `llm_` followed by 64 hexadecimal characters. The cache refuses malformed keys before file access.
- When a loaded entry contains a key field that differs from the requested key, the cache deletes the disk file and does not serve it.
- The cache resolves under `<DATA_DIR>/cache/llm` through settings, so `data.dir` and `DEVOPS_CLI_DATA_DIR` move it.
- `ai.cache.dir` is removed from configuration because the cache directory belongs to `data.dir`.
- The CLI commands `devops ai cache status` and `devops ai cache clear` build from settings and inspect `<DATA_DIR>/cache/llm`.
- A client created with `cache_enabled=False` neither reads nor writes the cache, even when a singleton cache exists.
- Model responses with empty or whitespace-only content are never cached.
- When the client rejects a cached entry on lookup, it deletes the entry from memory and disk.
- In `ModelProposal`, set `extra="forbid"` and make `priority`, `value`, and `effort` required fields.
- `chat_structured` does not store replies that fail schema validation in the cache.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `llm-response-cache`: how LLM responses are cached, validated, and isolated on the workstation filesystem.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/response_cache.py`: key validation, safe lookup, entry deletion, and settings-driven singleton initialization.
- `src/devops_cli/ai/client/unified.py`: empty-content caching exclusion, entry deletion on rejected lookup, and cache resolution.
- `src/devops_cli/config/settings.py` and `src/devops_cli/config/defaults.py`: remove `ai.cache.dir`.
- `src/devops_cli/roadmap/intake_model.py`: update `ModelProposal` schema.
- `tests/test_response_cache.py`, `tests/test_ai_client_structured.py`, `tests/test_review_untrusted_tree.py`, `tests/conftest.py`.

## Feasibility

- The code. At `origin/main` 30c6fa18, `LLMResponseCache` in `src/devops_cli/ai/response_cache.py` resolves `cache_dir` without key validation before file access.
- Key traversal. Testing with keys containing `../` or `/abs/` confirms path concatenation directly without canonical directory confinement.
- Settings alignment. Reviewing `settings.py` confirms `AICacheConfig` previously maintained a distinct `dir` setting decoupled from `DataConfig`.
- Structured schema. Testing `ModelProposal` confirms `extra="ignore"` permits invalid or echo schemas unless restricted by `extra="forbid"`.
- Unit tests verify all isolation requirements offline in temporary directories with local git repositories and stubs.

## Existing Tool Considered

- Disk caching: standard filesystem operations using Python `pathlib.Path` and stdlib `hashlib`.
- SQLite or third-party cache (such as `diskcache`): adds unnecessary binary dependencies and concurrency overhead for simple file-based responses.
- Building the validation logic in-tree requires minimal tokens and adds zero new runtime dependencies.
- Internal code removed: deletes `AICacheConfig.dir` and custom directory routing branches.
