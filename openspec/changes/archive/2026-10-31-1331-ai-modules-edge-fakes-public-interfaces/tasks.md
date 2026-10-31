# Tasks

- [x] 1. Write failing tests for `backend_type`, `probe_gateway_liveliness_and_models`, and `find_baseline_run`
- [x] 2. Remove mock fallback from `LLMClient.backend_type` in `src/devops_cli/ai/client/unified.py`
- [x] 3. Move gateway probe logic from `commands/ai_gateway.py` to `ai/gateway.py`
- [x] 4. Move baseline lookup logic from `commands/ai_runs.py` to `ai/run_store.py`
- [x] 5. Move benchmark execution logic from `commands/benchmark.py` to `ai/benchmark/`
- [x] 6. Merge `tests/ai/test_ai_repomap.py` into `tests/ai/test_repomap.py` and delete `tests/ai/test_ai_repomap.py`
- [x] 7. Clean gateway and review benchmark test cases from `tests/ai/test_run_store.py`
- [x] 8. Verify all tests pass, run static checks, and archive OpenSpec change
