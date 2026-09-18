# Task 127: Proactive Model Prewarming & VRAM Eviction Governance

**Issue**: [#127](https://github.com/dan-petty/devops-cli/issues/127)
**PR**: [#240](https://github.com/dan-petty/devops-cli/pull/240) (Merged)
**Status**: Completed
**Milestone**: `v0.2.19`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`, `scope/cli`

---

## 1. Description & Objectives

Local LLMs (Ollama) unload models from GPU VRAM after 5 minutes of inactivity by default (`keep_alive`). When a developer or automated review command triggers after idle time, loading a 26GB+ model into VRAM takes 15–45 seconds, causing CLI timeouts or perceived freezes. Conversely, when cluster nodes run low on VRAM for intensive tasks, models should be proactively evicted to free memory.

Objectives:
1. **Model Prewarming & Eviction Engine**: Enhance Ollama client mixin to dispatch prewarming calls to `/api/generate` with empty prompts, explicit model parameters, and customizable `keep_alive` durations (e.g. `1h`, `24h`, `forever`, or `0` for VRAM eviction).
2. **Cluster Multi-Node Support**: Dispatch prewarm and eviction calls concurrently across candidate cluster nodes (`ollama_urls`).
3. **CLI Command Integration**: Implement `devops ai prewarm` with `--model`, `--keep-alive`, `--all-nodes`, `--evict`, and `--json` support.
4. **FastMCP Tooling**: Expose `ai_prewarm_models` FastMCP tool for automated agents and workflows.
5. **Comprehensive Testing**: Provide unit test suite in `tests/test_ai_prewarm.py` with $\ge 90\%$ code coverage.

---

## 2. Key Deliverables

- `src/devops_cli/ai/client/ollama.py`: Parameterized prewarm and eviction methods on `OllamaProviderMixin`.
- `src/devops_cli/ai/client/unified.py`: Exposed `prewarm_models` and `evict_models` on `LLMClient`.
- `src/devops_cli/commands/ai.py`: `devops ai prewarm` CLI command with localized help strings and default constants.
- `src/devops_cli/ai/mcp/server.py`: `ai_prewarm_models` FastMCP tool.
- `tests/test_ai_prewarm.py`: Comprehensive unit test suite (15/15 passed).

---

## 3. Verification & Invariant Results

- **Unit Test Suite**: `uv run pytest tests/test_ai_prewarm.py` passes 15/15 tests covering single/multi-node prewarming, eviction payloads (`keep_alive=0`), asynchronous threading, CLI options (`--json`, `--evict`, `--url`), and FastMCP tool dispatch.
- **Architectural Invariants**: `uv run pytest tests/test_architectural_invariants.py` passes 8/8 tests.
- **Complexity Analysis**: `uv run devops scan complexity tests/test_ai_prewarm.py` confirms 100% compliance with $M \le 10$ and depth $\le 5$ ceilings.
- **Documentation Integrity**: `uv run pytest tests/test_docs.py` passes 21/21 checks confirming zero doc drift.
