# Tasks

## 1. Add the confinement registry and the resolver

Reads: `src/devops_cli/core/paths.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/ai/mcp/path_confinement.py` (new), `tests/ai/mcp/test_path_confinement.py` (new).

- [ ] 1.1 tests/ai/mcp/test_path_confinement.py: a kept path parameter resolves under the server root, and `../../etc/passwd` raises a ValidationError that names the parameter, and verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py` fails on the base
- [ ] 1.2 Write `src/devops_cli/ai/mcp/path_confinement.py` with `PATH_CONFINEMENTS`, a mapping from a command path tuple to the parameter names that it confines, and `confine_path_argument(path, name, value, root)`, which calls `safe_resolve_subpath` from `src/devops_cli/core/paths.py` with `error_cls=ValidationError`. Register `gh_pages_verify` and its `root_dir` there. Add the test module under `tests/ai/mcp/`, and verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py` passes

## 2. Confine a kept path argument in the tool function

Reads: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_mcp.py`.

- [ ] 2.1 tests/ai/mcp/test_mcp.py: the `gh_pages_verify` tool function refuses a `root_dir` outside the work tree and starts no command, and verify that `uv run devops ci test tests/ai/mcp/test_mcp.py` fails on the base
- [ ] 2.2 In `_create_tool_function` of `src/devops_cli/ai/mcp/generator.py`, after `bound.apply_defaults()`, call `confine_path_argument` for each parameter that `PATH_CONFINEMENTS` names, with the root of the server. Write the confined value back into `bound.arguments` so `_build_command_argv` gets it. Add the test to `tests/ai/mcp/test_mcp.py`, and verify that `uv run devops ci test tests/ai/mcp/test_mcp.py` passes

## 3. Publish no path option that the server can choose

Reads: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`.

- [ ] 3.1 tests/ai/mcp/test_fastmcp_contracts.py: the published schema of `ai_ast_graph` holds no `output_path` and the published schema of `k8s_security_stream` holds no `output`, and verify that `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py` fails on the base
- [ ] 3.2 Add an `_PATH_PARAM_RESTRICTIONS` entry for `("ai", "ast-graph")` and one for `("k8s", "security-stream")` in `src/devops_cli/ai/mcp/generator.py`, each with an `allowed` set that leaves out the output path and a `required` set. Extend `tests/ai/mcp/test_fastmcp_contracts.py` to assert the two absent properties, and verify that `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py` passes

## 4. Audit the published schema of every exposed tool

Reads: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/core/paths.py`. Changes: `tests/ai/mcp/test_path_confinement.py`.

- [ ] 4.1 In `tests/ai/mcp/test_path_confinement.py`, build each tool of `CONST_MCP_EXPOSURE_TABLE` through `_create_tool_function` of `src/devops_cli/ai/mcp/generator.py`, read the properties of its published schema, match a text property whose name holds a keyword of `_PATH_PARAM_KEYWORDS` from `src/devops_cli/core/paths.py`, and require a `PATH_CONFINEMENTS` entry. Assert that the set of path-like properties equals the registry entries, so a new path option fails the test with its tool name and parameter name, and verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py` passes

## 5. Document the published options of the three tools

Reads: `docs/MCP_TOOLS.md`, `src/devops_cli/ai/mcp/generator.py`. Changes: `docs/MCP_TOOLS.md`.

- [ ] 5.1 Remove the `output_path` row of `ai_ast_graph` and the `output` row of `k8s_security_stream` from `docs/MCP_TOOLS.md`, and note on `gh_pages_verify` that `root_dir` resolves under the work tree of the server, and verify that `uv run devops ci docs` passes
- [ ] 5.2 docs/MCP_TOOLS.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- No tool of a role table accepts a path outside a confined root.: group 2
- A test reads the published schema of every role tool and fails on an unconfined path parameter.: group 4

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
