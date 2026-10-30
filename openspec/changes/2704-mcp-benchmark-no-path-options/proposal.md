# Proposal

## Why

Issue #2704. The MCP tool `ai_benchmark` published the options `output`, `document` and `code`. The model that calls the tool fills them in, and no guard checked them. The generated tool refuses only a value that starts with a hyphen.

- `output` is a file path that the command writes. A model could choose a path, and the tool wrote the benchmark report there.
- `document` is a file that the embedding benchmark reads, and `code` is a directory tree that it reads. A model could name any readable file or tree. The command cut it into sections or code chunks and sent them to the model server as the text of embedding requests.

The cause is the same as in #2480, #2638 and #2639: input from a caller is used as configuration. #2638 closed the URL options of this tool and left these three open.

## What Changes

- The MCP tool `ai_benchmark` publishes no `output`, `document` and `code` option. A call that gives one fails at the argument contract, before any command runs. The command writes no file, reads no file and sends no request.
- The tool prints its report, as before. An embedding benchmark ranks the built-in corpus (`AGENTS.md` and the workspace specs).
- `devops ai benchmark` keeps `--output`, `--document` and `--code` for a person at the command line.
- A consumer sees the tool schema, so the change carries a spec delta in the capability `ai-benchmark`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-benchmark`: the tool schema lists fewer options, and a new requirement says that the tool takes no file path from a caller.

## Impact

- `src/devops_cli/ai/mcp/generator.py`: the entry of `("ai", "benchmark")` only.
- `tests/test_ai_benchmark_mcp_tool.py`.
- `docs/MCP_TOOLS.md` (generated).

## Feasibility

- On `origin/main` at `a3453463`, the new test showed the defect. It calls the tool through a FastMCP `Client`, with `ai.provider` set to `ollama` and `record_connects` of `tests/web_fakes.py`. A call with `output`, `document` or `code` set did not fail with a refusal of that parameter, and the schema of the tool listed the three names.
- `output` is not needed by a model. The tool returns the report on stdout in the format of `format_type`, and the command writes the file only when `--output` is set (`src/devops_cli/commands/benchmark.py`).
- `document` and `code` are not needed by a model. `EmbeddingBenchmarkRunner` falls back to the built-in corpus when both are unset (`AGENTS.md & Workspace Specs`). A person who wants their own corpus runs the command.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` is the existing way to publish fewer options, and #2480, #2634, #2637, #2638 and #2639 use it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- The tools of the generator have no path-confinement step. `safe_resolve_subpath` in `src/devops_cli/core/paths.py` exists and the roadmap and sandbox code use it, but no generated MCP tool does. Confinement to a workspace is rejected, see `design.md`.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator and the argument contract of the MCP server. Both exist. The change adds no code, no helper and no setting: it deletes three names from one allow list.

The change deletes the `output`, `document` and `code` options of the MCP tool.
