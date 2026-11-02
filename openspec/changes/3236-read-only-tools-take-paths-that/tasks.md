# Tasks

## 1. Extend parameter restrictions with confinement support

Reads: `src/devops_cli/core/paths.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/core/repo.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_path_confinement.py`.

- [ ] 1.1 In `tests/ai/mcp/test_path_confinement.py`, write tests asserting that a parameter configured in `"confined"` resolves under the server root. Assert that traversal attempts raise a `ValidationError` naming the parameter, and that the error message omits the absolute base path. Verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py` fails on the base.
- [ ] 1.2 In `src/devops_cli/ai/mcp/generator.py`, update `_create_tool_function` to read `"confined"` from `_PATH_PARAM_RESTRICTIONS`. Resolve repo-scoped roots via `find_repo_root()` or `Path.cwd()`, and resolve data-scoped roots via `load_settings().data.dir`. Apply `safe_resolve_subpath` and sanitize traversal error messages to omit absolute server paths. Verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py` passes.

## 2. Configure confinement and parameter pruning for exposed tools

Reads: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/commands/ai_ast.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/k8s/diagnostics.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_mcp.py`.

- [ ] 2.1 In `tests/ai/mcp/test_fastmcp_contracts.py` and `tests/ai/mcp/test_mcp.py`, assert that `ai_ast_graph` omits `output_path` and `k8s_security_stream` omits `output`. Assert that `gh_pages_verify` confines `root_dir`, and `ai_ast_graph` confines `target_dir`. Verify that `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_mcp.py` fails on the base.
- [ ] 2.2 In `src/devops_cli/ai/mcp/generator.py`, add `_PATH_PARAM_RESTRICTIONS` entries for `("ai", "ast", "graph")`, `("gh", "pages", "verify")`, and `("k8s", "security-stream")`. Restrict `output_path` and `output`, and configure `"confined"` roots for `target_dir` and `root_dir`. Verify that `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_mcp.py` passes.

## 3. Implement catalogue and role parameter schema audits

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/roles.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`. Changes: `src/devops_cli/config/constants.py`, `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp_roles.py`.

- [ ] 3.1 In `tests/ai/mcp/test_path_confinement.py` and `tests/ai/mcp/test_mcp_roles.py`, add tests asserting that path-like text parameters have confinement or allow-list entries. Assert that allow-list reasons have at least 30 characters without stale entries, and assert that `_JOB_ROLE_TOOLS` contain no unconfined file path parameters. Verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_mcp_roles.py` fails on the base.
- [ ] 3.2 Add `CONST_MCP_PATH_PARAMETER_ALLOWLIST` in `src/devops_cli/config/constants.py` defining verified reasons for non-file text parameters. Implement the full catalogue audit in `tests/ai/mcp/test_path_confinement.py` and the role audit in `tests/ai/mcp/test_mcp_roles.py`. Verify that `uv run devops ci test tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_mcp_roles.py` passes.

## 4. Update security policy and synchronize documentation

Reads: `SECURITY.md`, `docs/MCP_TOOLS.md`. Changes: `SECURITY.md`, `docs/MCP_TOOLS.md`.

- [ ] 4.1 Update `SECURITY.md` rule 11 to cite `_PATH_PARAM_RESTRICTIONS` confinement, `CONST_MCP_PATH_PARAMETER_ALLOWLIST`, and `tests/ai/mcp/test_path_confinement.py`.
- [ ] 4.2 Run `uv run devops docs generate --sync-readme` to regenerate `docs/MCP_TOOLS.md`. Verify that `uv run devops ci docs` passes.

## Criteria

- No tool of a role table accepts a path outside a confined root.: group 2
- A test reads the published schema of every role tool and fails on an unconfined path parameter.: group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
