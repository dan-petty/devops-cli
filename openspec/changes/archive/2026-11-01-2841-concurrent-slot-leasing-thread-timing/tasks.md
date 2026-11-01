# Tasks

- [x] Update `test_concurrent_slot_leasing_across_threads` in `tests/ai/client/test_ollama_dynamic_leasing.py` to synchronize the first three acquired slots and use `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 1 -->
- [x] Run test suite verification with `uv run devops ci test tests/ai/client/test_ollama_dynamic_leasing.py`. <!-- id: 2 -->
- [x] Validate static checks and OpenSpec change. <!-- id: 3 -->
