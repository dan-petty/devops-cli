# Proposal

## Why

The MCP tool ai_benchmark publishes the CLI help text of --models. That text shows a model@url example that the tool refuses since #2638. A model that copies the example gets an error. #2743 corrects the published schema.

## What Changes

- Add a module-level description string with plain model names for the ai_benchmark models parameter.
- Make the ai_benchmark MCP registration publish that string in place of the CLI help text.
- Keep the CLI help text of --models unchanged.
- Add a test that reads the ai_benchmark input schema and rejects a model@url form in the models description.
- Update the ai_benchmark models row in docs/MCP_TOOLS.md.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-benchmark`: MCP ai_benchmark models description lists plain model names, CLI ai benchmark models help keeps model@url

## Impact

- Code: `src/devops_cli/commands/ai.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/test_mcp_ai_benchmark_schema.py`

## Feasibility

- The issue cites `src/devops_cli/lang/en/help.py` and `docs/MCP_TOOLS.md`; the help catalog holds `HELP.benchmark.models` with the `model@url` example.
- The issue states that the MCP tool publishes that text as the `models` description; the change gives the tool its own description.
- First checks: `uv run devops mcp export-schemas --output-dir /tmp/mcp-schemas`, then read `ai_benchmark.json`; `uv run devops ai benchmark --help`; `uv run devops ci test tests/test_mcp_ai_benchmark_schema.py`.
- The inputs show no blocker. The change fits one pull request.

## Existing Tool Considered

No open, maintained tool covers a text fix in the project's own FastMCP tool registration. FastMCP is the library that publishes the schema, and the change edits the project's own code. Cost: about 2,000 tokens to build, 500 tokens a year to keep, 300 tokens to fix, and under one hour. It deletes no internal code.
