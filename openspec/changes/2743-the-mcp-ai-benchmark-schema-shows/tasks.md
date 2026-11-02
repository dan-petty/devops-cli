# Tasks

## 1. Publish plain model names in the ai_benchmark schema

Reads: `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/ai.py`, `docs/MCP_TOOLS.md`. Changes: `src/devops_cli/commands/ai.py`, `tests/test_mcp_ai_benchmark_schema.py` (new), `docs/MCP_TOOLS.md`.

- [ ] 1.1 tests/test_mcp_ai_benchmark_schema.py, and verify that `uv run devops ci test tests/test_mcp_ai_benchmark_schema.py` fails on the base
- [ ] 1.2 Write a failing test in `tests/test_mcp_ai_benchmark_schema.py`. The test builds the MCP server in process, reads the input schema of the `ai_benchmark` tool, and asserts that the `models` description holds no `model@url` form and no key or server rule. Add a module-level description string with plain model names to `src/devops_cli/commands/ai.py`. Make the `ai_benchmark` registration publish that string in place of `HELP.benchmark.models`. Keep the CLI help text unchanged. Update the `ai_benchmark` `models` row in `docs/MCP_TOOLS.md`, and verify that `uv run devops ci test tests/test_mcp_ai_benchmark_schema.py` passes
- [ ] 1.3 docs/MCP_TOOLS.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
