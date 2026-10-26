# Design

## Context

See proposal.md for motivation and problem analysis. The LLM response cache stores serialised JSON responses to avoid redundant model dispatches. It runs both as an in-memory dictionary and on the filesystem under the configured cache directory.

## Goals / Non-Goals

**Goals:**
- Confine all response cache file reads and writes strictly to `<cache_dir>/<key>.json`.
- Reject malformed or relative keys before filesystem access.
- Invalidate and delete any loaded cache file whose stored `key` does not match the requested key.
- Align cache directory resolution strictly with `data.dir` and `DEVOPS_CLI_DATA_DIR`.
- Ensure clients with `cache_enabled=False` bypass cache reads and writes completely.
- Exclude empty text responses and responses failing schema validation from the cache.

**Non-Goals:**
- Cryptographic signatures for cached entries (not needed once directory isolation and untrusted tree isolation prevent unauthorized writes).
- Backward compatibility for `ai.cache.dir` (pre-1.0 alpha software).

## Decisions

### Decision: Validate keys with strict pattern checking before filesystem access
Check that the requested key starts with `llm_` and contains exactly 64 hexadecimal characters. Any key failing this condition immediately returns `None` for lookups or is rejected on writes, without invoking any filesystem operations.
Rejected alternative: Path resolution and normalization checks (such as `resolve().is_relative_to()`). Evidence: Path resolution still touches the filesystem or parses arbitrary string paths, leaving potential edge cases or symlink complexities. Validating the key format upfront prevents arbitrary path creation entirely.

### Decision: Enforce key equality upon disk load
When loading a cached JSON file from disk, compare the entry `key` attribute against the requested key. If they differ, delete the disk file immediately and treat the lookup as a cache miss.
Rejected alternative: Overwriting the entry key on load. Evidence: Overwriting would allow malicious entries with bad keys to rewrite files or propagate invalid entries across calls.

### Decision: Re-root cache directly under `data.cache_dir / "llm"`
Remove `ai.cache.dir` from `AICacheConfig`. Build the global singleton cache using `settings.data.cache_dir / CONST_LLM_CACHE_DIR_NAME`.
Rejected alternative: Retaining `ai.cache.dir` with fallbacks. Evidence: Dual configuration paths caused the divergence between review runners and `ai cache status/clear` commands. Pre-1.0 policy removes obsolete shims.

### Decision: Delete rejected cached entries upon client lookup validation
In `unified.py: _check_chat_cache`, if `_validate_response_text(cached_entry.content, validator)` fails, delete the entry from both memory and disk via `cache.delete(cache_key)`.
Rejected alternative: Leaving rejected entries on disk until TTL expiry. Evidence: Leaving rejected entries caused repeated failed lookups, bumped access times, and prevented clean replacement.

### Decision: ModelProposal schema enforcement via Pydantic
Set `extra="forbid"` on `ModelProposal` and remove default values from `priority`, `value`, and `effort`.
Rejected alternative: Manual key validation in `chat_structured`. Evidence: Schema enforcement belongs in the Pydantic model definition. Adding ad-hoc dictionary validation in the client introduces fragile heuristics.

## Risks / Trade-offs

- [Risk] Existing tests that used arbitrary short test keys (such as `llm_1`) will fail key validation.
  → Mitigation: Update test fixtures in `tests/test_response_cache.py` to use valid 64-hex SHA-256 keys or helper methods.
