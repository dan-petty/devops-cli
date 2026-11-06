# Proposal

## Why

SECURITY.md rule 11 requires a path helper to confine a file path that a model gives to an MCP tool. #3236 asks that no tool of a role table accepts a path outside a confined root, and that a test finds an unconfined path parameter. The role tables of #3219 hold no path tool today, so the risk is a later edit: a person adds a tool name to a table and the tool carries a path option. Three tools that the tables leave out show the class: `ai_ast_graph` (`--output`, `--dir`), `k8s_security_stream` (`--output`) and `gh_pages_verify` (`--dir`). The `ops` role serves them, and a person on the command line chooses their paths.

## What Changes

- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gains an entry for `("ai", "ast", "graph")` and for `("k8s", "security-stream")`. The `output_path` option of the first and the `output` option of the second leave the published schema. The command of the first prints its graph, and the second prints its alerts, so the model needs no file.
- A new module `src/devops_cli/ai/mcp/path_confinement.py` holds two tables keyed by tool name. `PATH_CONFINEMENTS` names each kept path parameter (`target_dir` of `ai_ast_graph`, `root_dir` of `gh_pages_verify`). `NOT_A_FILE_PATH` names a text parameter whose name looks like a path and that is not a file path, with the reason (`target` of `security_intel_network` is a host or an address).
- `_create_tool_function` in `generator.py` calls a new `_check_path_confinement(tool_name, kwargs)` beside the other `_check_*` guards. It resolves each kept path argument through `safe_resolve_subpath` against the work tree of the server process, writes the resolved value back, and refuses an escape with a `ValidationError` that names the parameter. The root comes from the process and never from an argument.
- A new test `tests/ai/mcp/test_path_confinement.py` reads the published schema of every tool of every job role and fails on a text parameter whose name holds a keyword of `_PATH_PARAM_KEYWORDS` and that neither table names. It also covers the three tools above.
- The change carries a spec delta for the `mcp-tool-path-confinement` capability, because the published schema and the tool behavior are observable to a consumer.
- `docs/MCP_TOOLS.md` is regenerated: the `output_path` row of `ai_ast_graph` and the `output` row of `k8s_security_stream` go.
- The other tools of the `ops` role publish about 55 path parameters. Confining them is a separate item (see Workflow follow-up of `tasks.md`).
- The change fits one pull request.

## Capabilities

### New Capabilities

- `mcp-tool-path-confinement`: A tool publishes no path option that the server can choose, A kept path option resolves under a server root, The schema audit names an unconfined path parameter of a role tool

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp_tool_registry.py`

## Feasibility

- Command output, `git cat-file -e 4571d5f3:src/devops_cli/ai/mcp/roles.py` (the base of this branch) exits 0, and `git show --stat 69234732` shows #3233 adding it. The role tables exist, and `tools_for_role` in that file gives the tools of a role.
- Output of a script that lists the published schema of `tools_for_role(role, catalogue)` for each of `JOB_ROLES`: the planning role holds 28 tools, the implementation role 17 and the review role 16. One text parameter of them has a path-like name: `target` of `security_intel_network`, which is a host. No role tool takes a file path today, so the audit passes at once, and it fails when a later edit adds a path tool.
- The same script over the whole catalogue lists 60 tools that publish a path-like parameter, for example `ai_ingest_library.output_dir`, `scan_sbom.output_file`, `tf_apply.plan_file` and `vault_get.path`. The change confines only the three tools of the issue. It does not claim that every tool passes.
- `src/devops_cli/commands/ai_ast.py` shows `ast_graph_cmd` with `--dir` (`target_dir`) and `--output` (`output_path`); without `--output` it prints the graph. `src/devops_cli/commands/k8s/diagnostics.py` shows `security_stream_cmd` with `--output`. `src/devops_cli/commands/gh.py` shows `pages_verify_cmd` with `--dir` (`root_dir`). The command names are `ai ast graph`, `k8s security-stream` and `gh pages verify`; the issue text `ai ast-graph` is wrong.
- `_PATH_PARAM_RESTRICTIONS` holds no entry for the first two commands and `("gh", "pages", "verify")` needs none, because its option stays. `_introspect_command_parameters` skips every option that an entry does not allow, and `("ai", "benchmark")` already drops `output`, `document` and `code` this way (#2704).
- `safe_resolve_subpath` in `src/devops_cli/core/paths.py` raises on `..`, on an absolute path outside the base and on a symlink escape. The helper the fix needs exists.

## Existing Tool Considered

No open, maintained library confines the path parameters of an MCP server's tools: FastMCP publishes a tool schema and runs the function, and pydantic validates types, not containment. The change reuses `safe_resolve_subpath` in `src/devops_cli/core/paths.py` and the `_PATH_PARAM_RESTRICTIONS` table of `src/devops_cli/ai/mcp/generator.py`, so it adds no dependency. The written cost of the small module and the test is about 15,000 tokens to build, about 4,000 tokens per year to keep and fix, and one day elapsed. The change deletes no internal code: no tool function, registry entry or test is removed.
