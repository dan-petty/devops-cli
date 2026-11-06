# Design

## Decisions

- **Set the description in `_build_parameter_field` of `src/devops_cli/ai/mcp/generator.py`, from a table `_PARAM_DESCRIPTIONS` keyed by `(path, parameter name)`**: `_build_parameter_field` is the one place that sets a parameter description (line 169), so a tool built from any command takes the override with no change in `generate_mcp_tools`. `_introspect_command_parameters` already holds `path` and passes it to the lookup.
- **Keep the table apart from `_PATH_PARAM_RESTRICTIONS`**: `SECURITY.md` (rule 11 of MCP Tool Inputs) and the comment above the table name `_PATH_PARAM_RESTRICTIONS` as the list of options that a tool publishes, and `tests/ai/mcp/test_mcp.py` reads its `allowed` key only. A description in it would give the table a second job.
- **Hold the text in `HELP.mcp.benchmark_models`, in `src/devops_cli/lang/en/help.py`**: `generator.py` already takes its refusal text from the catalog (`ERRORS.mcp.model_names_endpoint`), and `CONTRIBUTING.md` puts emitted text in `lang/en/`. The example in the text is `qwen2.5:0.5b,llama3.1:8b`, the example of the command help without its `@url` entry, so the tool accepts it.
- **Put the tests in `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`**: it already builds `Client(mcp)` and reads the `ai_benchmark` schema, and `tests/ai/mcp/` mirrors `src/devops_cli/ai/mcp/` (`docs/TESTING.md`). The schema test takes the quoted example from the published description and gives it to `_check_model_endpoints`, so the test fails when the example is a form that the tool refuses, not only when it holds `@`.
- **Do not edit `docs/MCP_TOOLS.md` by hand**: `render_mcp_tools_markdown` writes it from the registered tools, so `devops docs generate --sync-readme` writes the new row. `devops docs check` fails when the file differs.

## Rejected alternatives

- **Change `HELP.benchmark.models` to plain model names**: `benchmark.py:118` feeds the same string to the command, and the command accepts `model@url` (the scenario "A person types the server" in `openspec/specs/ai-benchmark/spec.md`). A person would lose the form.
- **Strip the `model@url` sentences from the shared string when the tool is built**: the string has 4 sentences, and the example sits inside the first one. A strip rule must know that text, so it breaks when the text changes.
- **Add `models_mcp` to `BenchmarkCommandHelp`**: that dataclass feeds the options of `devops ai benchmark` (`benchmark.py:118`). The only reader of the new field would be `generator.py`, which already reads `HELP.mcp`.
- **Make the override in `src/devops_cli/commands/ai.py`**: the file only mounts `benchmark_app` (line 110). It holds no `ai_benchmark` registration, so no seam exists there.
- **Use `ArgTransform(description=...)` of FastMCP**: `Tool.from_tool` returns a second tool that forwards to the first one, so `generate_mcp_tools` must register the wrapper. The `Field` override needs one argument in a function that already exists.
