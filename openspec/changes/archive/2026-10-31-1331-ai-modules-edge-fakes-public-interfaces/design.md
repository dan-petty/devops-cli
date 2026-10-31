# Design

## Architecture Overview

This change aligns the remaining AI modules and tests with the testing architecture of issue #1307 and ADR 0005.

### 1. Mock Fallback Removal

`LLMClient.backend_type` in `src/devops_cli/ai/client/unified.py` previously checked if the provider attribute is a string and returned `"mock"` otherwise. This check is removed:
```python
@property
def backend_type(self) -> str:
    """Return the AI provider backend type (e.g. ollama, claude, copilot, openai)."""
    p = getattr(self._config, "provider", "ollama")
    return str(p or "ollama")
```

### 2. Domain Logic Movement

Command modules must remain thin CLI adapters:
- `probe_gateway_liveliness_and_models(base_url: str, headers: dict[str, str], timeout: float)` moves from `src/devops_cli/commands/ai_gateway.py` to `src/devops_cli/ai/gateway.py`.
- `find_baseline_run(subject_or_run: str, mechanism: Mechanism | None)` moves from `src/devops_cli/commands/ai_runs.py` to `src/devops_cli/ai/run_store.py`.
- Benchmark execution functions move from `src/devops_cli/commands/benchmark.py` to `src/devops_cli/ai/benchmark/`.

### 3. Test File Consolidation and Cleaning

- `tests/ai/test_ai_repomap.py` merges into `tests/ai/test_repomap.py`, with CLI tests using the shared `cli` fixture.
- Gateway and review test cases in `tests/ai/test_run_store.py` that do not test run-store behavior are removed or refactored to focus purely on run store storage and retrieval.
