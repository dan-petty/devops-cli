# Tasks

## 1. Duration of a model request

Kind: behavior. Reads: `src/devops_cli/ai/client/factory.py`, `tests/ai/client/test_agent_factory.py`. Changes: `src/devops_cli/ai/client/factory.py`.

- [x] 1.1 Write the tests of the duration, of the failed request, of the kept fields and of the mean duration, and watch them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Time each request in the hooks of `build_agent`
  - Verification: `$ uv run pytest -q tests/ai/client/test_agent_factory.py`
