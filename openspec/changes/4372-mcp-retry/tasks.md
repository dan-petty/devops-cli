# Tasks

## 1. Retry the first MCP connection

Reads: `src/devops_cli/roadmap/mcp.py`. Changes: the same file, `src/devops_cli/config/constants.py`, and `tests/roadmap/test_roadmap_mcp_connect_retry.py`.

- [ ] 1.1 Add the three constants.
- [ ] 1.2 Retry a refused connection in `__aenter__` with tenacity.
- [ ] 1.3 Add the four tests.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_mcp_connect_retry.py tests/roadmap/test_roadmap_mcp.py` passes
