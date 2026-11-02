# Design

## Decisions

- **Give the ai_benchmark MCP tool its own models description in `src/devops_cli/commands/ai.py`.**: The CLI help must keep the model@url form, and the published schema must not show it.
- **Test the exported schema, not the help string.**: The issue asks for the published schema, and the CLI help keeps model@url.
- **Update the ai_benchmark models row in `docs/MCP_TOOLS.md`.**: The document shows the published schema row.

## Rejected alternatives

- **Change `HELP.benchmark.models` to plain model names.**: The issue says the CLI help keeps the model@url form for a person; one string feeds both surfaces.
- **Strip the model@url sentences from the shared string at publish time.**: The issue's proposed design rejects parsing a shared string as fragile and hard to test.
- **Add a `models_mcp` field to `BenchmarkCommandHelp`.**: The issue's proposed design rejects a second help-catalog field for a value that only the MCP tool uses.
