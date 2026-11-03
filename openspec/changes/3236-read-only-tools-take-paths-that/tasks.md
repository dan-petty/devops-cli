# Tasks

## 1. Add the confinement tables and the guard

Reads: `src/devops_cli/core/paths.py`, `src/devops_cli/ai/mcp/generator.py`.
Changes: `src/devops_cli/ai/mcp/path_confinement.py` (new), `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_mcp.py`.

- [ ] 1.1 In `tests/ai/mcp/test_mcp.py`, write tests that the `gh_pages_verify` tool refuses `../../etc/passwd` and the `ai_ast_graph` tool refuses `/etc` with a `ValidationError` that names the parameter and starts no command, and that `docs` resolves under the work tree. Verify `uv run devops ci test tests/ai/mcp/test_mcp.py` fails on the base
- [ ] 1.2 Write `src/devops_cli/ai/mcp/path_confinement.py` with `PATH_CONFINEMENTS` (`ai_ast_graph`: `target_dir`; `gh_pages_verify`: `root_dir`) and `NOT_A_FILE_PATH` (`security_intel_network`: `target`, with the reason). In `generator.py`, add `_check_path_confinement(tool_name, kwargs)`, which calls `safe_resolve_subpath` with `error_cls=ValidationError` against the work tree of the process and writes the resolved value back, and call it in `_create_tool_function` beside `_check_oidc_token_reference`. Verify `uv run devops ci test tests/ai/mcp/test_mcp.py` passes

## 2. Publish no output path for two tools

Reads: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`.
Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`.

- [ ] 2.1 In `tests/ai/mcp/test_fastmcp_contracts.py`, assert that the schema of `ai_ast_graph` holds no `output_path` and that of `k8s_security_stream` holds no `output`. Verify `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py` fails on the base
- [ ] 2.2 Add `_PATH_PARAM_RESTRICTIONS` entries for `("ai", "ast", "graph")` and `("k8s", "security-stream")` that allow every option of the command but the output option. Verify `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py` passes

## 3. Audit the path parameters of the role tools

Reads: `src/devops_cli/ai/mcp/roles.py`, `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/core/paths.py`.
Changes: `tests/ai/mcp/test_path_confinement.py` (new).

- [ ] 3.1 In `tests/ai/mcp/test_path_confinement.py`, take the catalogue of `mcp`, apply `tools_for_role` for each of `JOB_ROLES`, and match each text property whose name holds a keyword of `_PATH_PARAM_KEYWORDS`. Require an entry in `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH`, and fail with the tool and parameter name. Add a case that a synthetic tool with `output_path` fails. Verify `uv run devops ci test tests/ai/mcp/test_path_confinement.py` passes

## 4. Document the published options

Reads: `docs/MCP_TOOLS.md`.
Changes: `docs/MCP_TOOLS.md`.

- [ ] 4.1 Run `uv run devops docs generate --sync-readme`, and verify `uv run devops ci docs` passes

## Criteria

- No tool of a role table accepts a path outside a confined root.: group 3
- A test reads the published schema of every role tool and fails on an unconfined path parameter.: group 3
- Tests cover the path options of `ai_ast_graph`, `k8s_security_stream` and `gh_pages_verify`.: group 1, group 2
- The confinement root is not a tool argument.: group 1

## Workflow follow-up

- Confine or drop the path parameters of the other 60 tools of the `ops` role, and extend the audit to them: #3300.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
