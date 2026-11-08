# Tasks

## 1. Settings and Exceptions

- [x] 1.1 Add MCP settings and credentials
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py`
- [x] 1.2 Add RoadmapMcpUnavailableError
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_mcp.py`

## 2. MCP Client and Toolset

- [x] 2.1 Implement RoadmapMcpToolset with local tool precedence and timeout
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_mcp.py`
- [x] 2.2 Wire MCP client into StageTools and ToolboxClient
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`
- [x] 2.3 Wire MCP client into implement step
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_mcp.py`

## 3. Telemetry, RunTrace and Evals

- [x] 3.1 Record remote call outcome and timeout in RunTrace
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py`
- [x] 3.2 Run and report stage and implement evals
  - Verification: `$ uv run devops roadmap eval stage --replay && uv run devops roadmap eval implement --check-only`
