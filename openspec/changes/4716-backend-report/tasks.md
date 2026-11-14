# Tasks

## 1. Pass the served backend

Reads: `src/devops_cli/ai/client/factory.py`. Changes: the same file and `tests/ai/client/test_agent_factory.py`.

- [ ] 1.1 Pass `served_by` in the spend hook.
- [ ] 1.2 Add the backend report test and point the price tests at a hosted backend.
  - Verification: `$ uv run devops ci test tests/ai/client/test_agent_factory.py` passes
