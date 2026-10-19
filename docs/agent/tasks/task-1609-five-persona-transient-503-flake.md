# Task: Fix Five-Persona Transient-503 Review Test Flake (#1609)

**Issue**: [#1609](https://github.com/dan-petty/devops-cli/issues/1609)
**Scope**: scope/ai
**Feasibility**: Verified by testing `LLMClient._retry_chat_dispatch` exception mapping and `test_five_personas_with_one_transient_503_sees_exactly_six_calls` with explicit cache and settings isolation. Verified that non-transport dispatch exceptions no longer report false "Cannot connect" errors and that the multi-persona review stall tests pass cleanly across concurrent pytest-xdist runs.

## Description

In CI test runs under concurrent worker load, `test_five_personas_with_one_transient_503_sees_exactly_six_calls` in `tests/test_gateway_review_stall.py` intermittently failed with:
`assert (6, 'failed', "Review: Cannot connect to AI provider API...", []) == (6, 'reviewed', None, [])`

Two distinct root causes were identified:
1. **AI Client Catch-All Exception Masking**: `LLMClient._retry_chat_dispatch` in `src/devops_cli/ai/client/unified.py` caught `except Exception as exc:` and unconditionally transformed all unexpected non-AI errors into `_connection_error(exc)` ("Cannot connect to AI provider API..."). This masked real exceptions (such as file not found, key errors, or concurrency errors during response parsing or cache writes) as network connection failures, misleading users and obscuring test diagnostics.
2. **Shared State & Cache Eviction Concurrency**:
   - `test_five_personas_with_one_transient_503_sees_exactly_six_calls` did not reset `_GLOBAL_LLM_CACHE` or settings cache before or after execution, leaving the global response cache pointing to stale or removed test directories from prior tests in the same worker, and had `cache_enabled` left as True across 5 concurrent persona threads.
   - `_evict_excess_disk_files` in `src/devops_cli/ai/response_cache.py` sorted disk files by `p.stat().st_mtime` without catching `OSError` if a file was unlinked between `glob()` and `stat()`, causing unhandled `FileNotFoundError` during disk cache eviction under parallel runs.

Remediation applied:
- Updated `LLMClient._retry_chat_dispatch` in `src/devops_cli/ai/client/unified.py` to map only `httpx2.TransportError` (and its subclasses) to connection errors, while wrapping other unexpected exceptions in `AIClientError(f"{type(exc).__name__}: {exc}")` naming the actual exception type.
- Made `_evict_excess_disk_files` in `src/devops_cli/ai/response_cache.py` race-safe by using a safe mtime accessor and handling `OSError`.
- Isolated `test_five_personas_with_one_transient_503_sees_exactly_six_calls` and `test_transport_answers_400_once_fails_without_second_attempt_and_reports_status` in `tests/test_gateway_review_stall.py` with `reset_settings_cache()`, `reset_llm_response_cache()`, and `cache_enabled=False`.
- Added unit tests in `tests/test_ai_client_retries.py` verifying that non-transport exceptions do not report "Cannot connect" and that transport errors correctly report connection errors.

## Acceptance Criteria

- [x] `LLMClient._retry_chat_dispatch` maps only `httpx2.TransportError` and subclasses to `_connection_error`.
- [x] Non-transport exceptions during dispatch propagate or wrap in `AIClientError` naming the exception type.
- [x] Unit tests verify non-transport dispatch exceptions do not report "Cannot connect".
- [x] Disk cache eviction in `LLMResponseCache` safely tolerates concurrently unlinked files.
- [x] `test_five_personas_with_one_transient_503_sees_exactly_six_calls` isolates settings and response cache state and passes reliably.
- [x] Changelog fragment `changelog.d/1609.md` added.

## Deliverables

- [x] Modified `src/devops_cli/ai/client/unified.py` to separate transport error handling from generic exception wrapping.
- [x] Modified `src/devops_cli/ai/response_cache.py` to add race-safe disk cache file mtime inspection and error handling.
- [x] Added unit tests in `tests/test_ai_client_retries.py`.
- [x] Added cache and settings isolation to `tests/test_gateway_review_stall.py`.
- [x] Added `docs/agent/tasks/task-1609-five-persona-transient-503-flake.md`.
- [x] Added `changelog.d/1609.md`.
