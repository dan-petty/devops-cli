# Tasks

## 1. Publish plain model names in the ai_benchmark schema

Kind: behavior. Reads: `src/devops_cli/ai/mcp/generator.py` lines 29 to 90 (`_PATH_PARAM_RESTRICTIONS`), 166 to 210 (`_build_parameter_field`, `_introspect_command_parameters`) and 289 to 303 (`_check_model_endpoints`), `src/devops_cli/lang/en/help.py` lines 899 to 909 (`MCPCommandHelp`) and 1850 to 1855 (`BenchmarkCommandHelp.models`). Changes: `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/help.py`.

- [x] 1.1 In `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, add a class `TestBenchmarkToolPublishesPlainModelNames` with `@pytest.mark.usefixtures("keyring_store")`, as the class above it has. One async test lists the tools with `Client(mcp)` and reads `input_schema["properties"]["models"]["description"]` of `ai_benchmark`. It asserts that the text holds none of `@`, `model@url`, `api_base_url`, `gateway_url` and `key`. It takes the first quoted example of the text (`re.search(r"'([^']+)'", text)`), asserts that it exists, and gives it to `_check_model_endpoints(("ai", "benchmark"), {"models": example})` from `devops_cli.ai.mcp.generator`, which must not raise. One sync test asserts that `HELP.benchmark.models` holds `llama3.1:8b@http://gpu2:11434` and `The MCP tool refuses a model@url.` (the guard of the second requirement; it passes on the base). Verify that `uv run devops ci test tests/ai/mcp/test_ai_benchmark_mcp_tool.py` fails on the base
- [x] 1.2 In `src/devops_cli/lang/en/help.py`, add `benchmark_models: str` to `MCPCommandHelp` with the value `Comma-separated candidate model names (e.g. 'qwen2.5:0.5b,llama3.1:8b'). Each model runs on the servers that the configuration names.`, written as two implicitly joined strings. In `src/devops_cli/ai/mcp/generator.py`, import `HELP` from `devops_cli.lang`, and add `_PARAM_DESCRIPTIONS: dict[tuple[tuple[str, ...], str], str]` with the entry `(("ai", "benchmark"), "models"): HELP.mcp.benchmark_models`, and a comment that says why the table exists. Give `_build_parameter_field` the parameter `description: str | None = None`, and set `"description": description or _clean_text(getattr(param, "help", None) or "")`. In `_introspect_command_parameters`, pass `_PARAM_DESCRIPTIONS.get((path, p.name))` to it. Leave `HELP.benchmark.models` and `_PATH_PARAM_RESTRICTIONS` as they are. Verify that `uv run devops ci test tests/ai/mcp/test_ai_benchmark_mcp_tool.py` passes
- [x] 1.3 Check the tests that must keep passing: `test_mcp_tool_schema_and_argv_parsing` of `tests/ai/mcp/test_mcp.py`, `test_no_tool_text_names_a_flag_that_the_tool_does_not_publish` of `tests/ai/mcp/test_fastmcp_contracts.py`, and `tests/lang/test_language_catalogs.py`. Verify that `uv run devops ci test tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_contracts.py tests/lang/test_language_catalogs.py` passes

## 2. Regenerate the MCP tool reference

Kind: documentation. Reads: `docs/MCP_TOOLS.md` lines 187 to 205 (`ai_benchmark`). Changes: `docs/MCP_TOOLS.md` (generated).

- [x] 2.1 Run `uv run devops docs generate --sync-readme`. Only the `models` row of `ai_benchmark` in `docs/MCP_TOOLS.md` changes: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` and `README.md` keep the text of the command help. Verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
