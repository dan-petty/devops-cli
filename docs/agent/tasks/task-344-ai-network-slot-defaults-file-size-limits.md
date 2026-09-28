# Task 344: Centralize AI Network Slot Leasing Defaults & Elevate File Size Limits to Minimum 50 MiB

**Issue**: [#344](https://github.com/dan-petty/devops-cli/issues/344)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

Arbitrary magic numbers and defaults were previously declared inline in `src/devops_cli/ai/client/network.py` and across parsing/scanner modules (e.g., `max_parallel=2`, timeout fallback `300.0s`, poll interval `0.5s`, and disparate file size limits ranging from 2 MiB to 20 MiB) rather than in centralized configuration submodules (`defaults.py`, `constants.py`).

This task centralizes all slot leasing defaults, establishes standardized constants, and increases all pre-flight and ingestion file size limits across the codebase to a minimum of 50 MiB (`50 * 1024 * 1024` = 52,428,800 bytes) to accommodate modern large-scale enterprise repositories, monorepos, and dense multi-language codebases.

#### Key Deliverables:
- [x] **Config Submodule Centralization**:
  - Added `CONST_AI_ALLOW_PRIVATE_NETWORK_ENV` in `src/devops_cli/config/constants.py`.
  - Added `DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS = 900.0` and `DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS = 2.0` in `src/devops_cli/config/defaults.py`.
  - Added `DEFAULT_AI_MAX_RESPONSE_BYTES = 50 * 1024 * 1024` (50 MiB) in `src/devops_cli/config/defaults.py`.
- [x] **Network & Ollama Slot Leasing Refactor**:
  - Bound `acquire_ollama_slot`, `track_ollama_url`, and `_wait_for_slot` in `src/devops_cli/ai/client/network.py` to centralized defaults (`DEFAULT_OLLAMA_MAX_PARALLEL`, `DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS`, `DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS`).
  - Bound `read_limited_json` in `network.py` and `unified.py` to `DEFAULT_AI_MAX_RESPONSE_BYTES`.
  - Updated `_preload_single_ollama_url` and `_ollama_stream` in `src/devops_cli/ai/client/ollama.py` to use `DEFAULT_AI_PREWARM_KEEP_ALIVE` and `DEFAULT_OLLAMA_MAX_PARALLEL`.
  - Unified `_ALLOW_PRIVATE_NETWORK_ENV` across `validation.py` and `network.py` using `CONST_AI_ALLOW_PRIVATE_NETWORK_ENV`.
- [x] **File Size Limit Elevation (Minimum 50 MiB)**:
  - Elevated `DEFAULT_MAX_AST_FILE_SIZE_BYTES` to 50 MiB (`50 * 1024 * 1024`).
  - Elevated `DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES` to 50 MiB (`50 * 1024 * 1024`).
  - Elevated `DEFAULT_JSON_REPAIR_MAX_LENGTH` to 50 MiB (`50 * 1024 * 1024`).
  - Elevated `DEFAULT_TOOL_MAX_BYTES_LIMIT` to 50 MiB (`50 * 1024 * 1024`).
  - Elevated `CONST_MAX_INSPECT_FILE_SIZE_BYTES` to 50 MiB (`50 * 1024 * 1024`).
  - Elevated `MAX_CHUNK_FILE_SIZE_BYTES` in RAG chunker to 50 MiB (`50 * 1024 * 1024`).
  - Updated AST parser engine, repository scanner, document chunker, drift detector, indexer, workspace loader, and milestones parser to adhere to the 50 MiB minimum.
  - Updated `AGENTS.md` defensive containment guidelines to reflect the 50 MiB cap.
- [x] **Test Verification & Quality Gates**:
  - Enhanced `tests/test_ollama_dynamic_leasing.py` to assert that slot leasing, URL tracking, and JSON reading helpers bind to centralized defaults.
  - Verified 100% passing across unit test suites.
  - Verified cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% compliance with Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Unit Tests**: 100% passed in `tests/test_ollama_dynamic_leasing.py`, `tests/test_ai_request_priority.py`, `tests/test_ai_inspection.py`, and `tests/test_consolidation_ast_cache.py`.
- **Architectural Invariants**: Complexity check passed ($M \le 10$, depth $\le 5$).
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
