# Proposal

## Why

The MCP tool `ai_benchmark` publishes the help text of the option `--models` as the description of its `models` parameter (#2743). That text gives the example `llama3.1:8b@http://gpu2:11434` and the key and server rules of `model@url`. The tool has refused a `model@url` entry since #2638, so a model that copies the example gets an error. #2743 gives the tool a description of its own, and leaves the help text of the command as it is.

## What Changes

- Add `benchmark_models` to `MCPCommandHelp` in `src/devops_cli/lang/en/help.py`. It lists plain model names, and its example is one that the tool accepts.
- Add a table `_PARAM_DESCRIPTIONS` to `src/devops_cli/ai/mcp/generator.py`, keyed by the command path and the parameter name. `_build_parameter_field` takes the description from the table before it takes the help text of the option. The first entry is `(("ai", "benchmark"), "models")`.
- Keep `HELP.benchmark.models`. The command `devops ai benchmark` keeps the `model@url` form for a person.
- Add tests to `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`. One reads the published schema of `ai_benchmark` and checks the `models` description. One checks that the help text of the command keeps `model@url`.
- Regenerate `docs/MCP_TOOLS.md` with `devops docs generate --sync-readme`. The row of `models` is generated from the registered tool, so no hand edit is needed. `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` do not change.
- The change alters the published schema of a tool, which a consumer observes. So it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-benchmark`: the `models` description of the MCP tool lists plain model names, and the help text of the command keeps `model@url` (two ADDED requirements, no existing requirement changes)

## Impact

- Code: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/help.py`
- Document (generated): `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`
- Dependencies: none. #2638 and #2704 are closed. A search of the open issues and pull requests for `2743`, `ai_benchmark` and `MCP description generator.py` finds only #2743 itself. The open changes `2651`, `2670` and `2579` name `src/devops_cli/ai/mcp/generator.py` or `help.py` only to read them, and none edits the same lines.

## Feasibility

I ran these commands at `ff9ad065` (main), with devops-cli 0.46.1, fastmcp 4.1.2 and a temporary `HOME`.

1. The published description. `devops mcp export-schemas --output-dir <dir>` wrote 146 schemas. In `ai_benchmark.json`, `properties.models.description` is:

   `Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434'). A model@url runs on that server, which gets the AI key only when it is the configured api_base_url, gateway_url or provider API. The output and the reports name it model@host[:port]. The MCP tool refuses a model@url.`

   It is the text of `HELP.benchmark.models` (`src/devops_cli/lang/en/help.py:1850-1855`), so the premise holds.
2. The source of that text. `_build_parameter_field` in `src/devops_cli/ai/mcp/generator.py:169` sets `"description": _clean_text(getattr(param, "help", None) or "")`, and `src/devops_cli/commands/benchmark.py:118` sets `help=HELP.benchmark.models`. `src/devops_cli/commands/ai.py:110` only mounts `benchmark_app`, so that file has no seam for the description.
3. The tool refuses the example. `_check_model_endpoints(("ai", "benchmark"), {"models": "llama3.1:8b@http://gpu2:11434"})` raises `ValidationError: Invalid value for 'models': an entry with '@' names the server that gets the requests of the benchmark, which only the command line may choose. Name each model alone; it runs on the configured servers`.
4. The docs row follows the registered tool. `_mcp_tool_to_doc` (`src/devops_cli/docs/generator.py:183`) reads `tool.parameters`, so `docs/MCP_TOOLS.md` is generated from the schema of the tool.
5. The plan works. In a scratch clone I made the change of group 1 and ran `uv run devops ci test tests/ai/mcp/test_ai_benchmark_mcp_tool.py tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_contracts.py tests/lang/test_language_catalogs.py`: 267 passed. With the source change removed and the new tests kept, the same file gives `1 failed, 14 passed`: the schema test fails, and the guard of the command help passes. After `devops docs generate --sync-readme`, `git status` lists only `docs/MCP_TOOLS.md`, and its `models` row reads `Comma-separated candidate model names (e.g. 'qwen2.5:0.5b,llama3.1:8b'). Each model runs on the servers that the configuration names.` `devops docs check` then prints `All documentation files are up to date.` I removed the scratch change.
6. Acceptance criteria. The issue has no `Acceptance criteria` list outside the block of the refine job, so `acceptance_criteria(body)` finds none and the tasks need no `## Criteria` mapping.

## Existing Tool Considered

FastMCP 4.1.2 (already a dependency) has `ArgTransform(description=...)` and `Tool.from_tool(..., transform_args=...)`. The change does not use it: `Tool.from_tool` builds a second tool that forwards to the first, and `generate_mcp_tools` would register that wrapper in place of the function that `server.tool(...)` takes now. The pydantic `Field(description=...)` that `_build_parameter_field` already builds is the seam, and it needs one more argument. No other open, maintained library covers this need. The change builds 1 table and 1 argument, and deletes no internal code. Cost: about 3,000 tokens to build, about 1,000 tokens to keep (one more entry for each future override), about 2,000 tokens to fix, and under one hour.
