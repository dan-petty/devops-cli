# Proposal

## Why

Some MCP tools that are marked read-only publish a path option (`ai_ast_graph --output_path`, `k8s_security_stream --output`, `gh_pages_verify --root_dir`). The model that calls the tool chooses the value, so the server opens or writes a path outside its work tree. SECURITY.md rule 11 requires a path helper to confine a path that a model gives. #3236 asks for the confinement and for a test that finds an unconfined path option.

## What Changes

- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gains an entry for each exposed command that has a path option, so the tool publishes only the options that its entry allows.
- A new module `src/devops_cli/ai/mcp/path_confinement.py` holds the confinement registry: each kept path parameter with the server root that confines it, resolved through `safe_resolve_subpath`.
- The tool function of `generator.py` confines each kept path argument against its server root before it builds the command line, and refuses a value that escapes with a `ValidationError`.
- `ai_ast_graph` publishes no `output_path`: the command writes its graph to the data directory under the server-chosen name.
- `k8s_security_stream` publishes no `output`: the stream is printed, and no file is written.
- `gh_pages_verify` keeps `root_dir` and confines it under the work tree root.
- A new test `tests/ai/mcp/test_path_confinement.py` reads the published schema of every exposed tool and fails on a path-like text parameter that the registry does not name.
- The change carries a spec delta for the `mcp-tool-path-confinement` capability, because the published schema and the tool behavior are observable to a consumer.
- `docs/MCP_TOOLS.md` lists the options of the three tools without their removed path options.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `mcp-tool-path-confinement`: A tool publishes no path option that the server can choose, A kept path option resolves under a server root, The schema audit names an unconfined path parameter

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp.py`, `tests/ai/mcp/test_fastmcp_contracts.py`

## Feasibility

- `search_code` for `_PATH_PARAM_RESTRICTIONS` returned the table in `src/devops_cli/ai/mcp/generator.py`, and the file holds no entry for `("ai", "ast-graph")`, `("k8s", "security-stream")` or `("gh", "pages-verify")`, so every option of those commands is published: "    restrictions = _PATH_PARAM_RESTRICTIONS.get(path)" then "        if restrictions and p.name not in restrictions["allowed"]:". The premise holds.
- `search_code` for `output_path` returned the option of the `ai ast-graph` command, and `search_code` for `root_dir` returned the option of `devops gh pages verify`, so the two examples of the issue are real options at this commit.
- `read_file src/devops_cli/core/paths.py` showed `safe_resolve_subpath` at line 35, with the containment check "    if not resolved.is_relative_to(base):" and the error "Path traversal detected: path '{subpath}' escapes base directory '{base}'.". The helper the fix needs exists.
- `read_file src/devops_cli/ai/mcp/generator.py` showed `generate_mcp_tools` registering each tool from `CONST_MCP_EXPOSURE_TABLE` with `annotations={"readOnlyHint": read_only}`, so the read-only flag and the published schema come from that table.
- `search_code` for `roles` under `src/devops_cli/ai/mcp` found no role table, and the probe reports that `src/devops_cli/ai/mcp/roles.py` is no file of the staging commit and that no commit deleted or renamed it. The role tables of #3219 are not in this base, so the audit reads the exposed tool set of `CONST_MCP_EXPOSURE_TABLE` and the confinement registry, and it covers the role tools as soon as they are built on the same table.
- First checks against the real system: `uv run devops ai ast-graph --help` lists the options of the command; `uv run devops k8s security-stream --help` lists its options; `uv run devops gh pages-verify --help` lists `--root_dir`; `uv run devops ci test tests/ai/mcp/test_path_confinement.py` runs the new schema audit; `uv run devops ci test tests/ai/mcp/test_mcp.py` runs the existing generator tests.

## Existing Tool Considered

No open, maintained library confines the path parameters of an MCP server's tools: FastMCP publishes a tool schema and runs the function, and pydantic validates types, not containment. The change reuses `safe_resolve_subpath` in `src/devops_cli/core/paths.py` and the `_PATH_PARAM_RESTRICTIONS` table of `src/devops_cli/ai/mcp/generator.py`, so it adds no dependency. The written cost of the small module and the test is about 15,000 tokens to build, about 4,000 tokens per year to keep and fix, and one day elapsed. The change deletes no internal code: no tool function, registry entry or test is removed.
