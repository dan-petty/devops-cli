## 1. Dockerfile MCP Server Target

- [x] 1.1 Add the mcp-server stage inheriting runner with kubectl and helm
  - Verification: `$ uv run pytest tests/invariants/test_mcp_server_image.py` passes

## 2. CI Workflow Gate

- [x] 2.1 Add mcp-server-image job and update workflow invariants
  - Verification: `$ uv run pytest tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py` passes

## 3. Invariants and Quality Gate

- [x] 3.1 Verify all tests and OpenSpec gates pass
  - Verification: `$ uv run devops ci --only openspec` passes
