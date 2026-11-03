# Design

## Decisions

- **Keep `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` as the single registry for MCP parameter publication and path confinement.**: Consolidating allowed options and path confinement in one dictionary avoids synchronization drift and satisfies SECURITY.md rule 11.
- **Extend `_PATH_PARAM_RESTRICTIONS` entries with an optional `"confined"` mapping that pairs parameter names with root anchor types (`"repo"` or `"data"`).**: `"repo"` resolves against the repository root from `find_repo_root()` (falling back to current working directory); `"data"` resolves against `settings.data.dir`.
- **Remove `output_path` from `ai_ast_graph` and `output` from `k8s_security_stream`, while keeping `target_dir` of `ai_ast_graph` and `root_dir` of `gh_pages_verify` confined to the repository root.**: Commands print to standard output when output options are omitted. Read parameters remain useful to callers when confined strictly within the repository tree.
- **Enforce path confinement in `_create_tool_function` before `_build_command_argv` executes.**: Calling `safe_resolve_subpath` inside the tool function intercepts traversal escapes early, replaces the argument with the confined path, and prevents invalid paths from reaching command subprocesses.
- **Sanitize traversal error messages returned to callers to omit absolute server paths.**: The tool function catches traversal exceptions and raises a `ValidationError` containing only the parameter name and input value, preventing disclosure of internal server directory paths to the model.
- **Follow the allow-list audit pattern from `test_mcp_tool_secrets.py` for catalogue path verification.**: Add `CONST_MCP_PATH_PARAMETER_ALLOWLIST` in `constants.py` with explanatory reasons of at least 30 characters for non-file text parameters matching `_PATH_PARAM_KEYWORDS`.
- **Implement a dual-scope audit in tests.**: `tests/ai/mcp/test_path_confinement.py` tests all exposed tools from `mcp._list_tools()` against `_PATH_PARAM_RESTRICTIONS` and the allow-list. `tests/ai/mcp/test_mcp_roles.py` tests that `_JOB_ROLE_TOOLS` contain no unconfined file path parameters.
- **Update documentation and security guidelines through automated generation.**: Update `SECURITY.md` rule 11 to cite the confinement registry and test. Run `uv run devops docs generate --sync-readme` to synchronize `docs/MCP_TOOLS.md`.

## Rejected Alternatives

- **Add a separate `PATH_CONFINEMENTS` registry module.**: Creating a second registry duplicates command keys and creates maintenance drift with `_PATH_PARAM_RESTRICTIONS`.
- **Permit callers to specify the confinement root parameter.**: Allowing the calling model to choose the root anchor directory would break the security boundary.
- **Drop `target_dir` and `root_dir` instead of confining them.**: These options provide essential functionality for analyzing specific repository directories; confining them through `safe_resolve_subpath` eliminates traversal risks without removing functionality.
- **Rely solely on the `readOnlyHint` annotation without argument validation.**: The `readOnlyHint` annotation informs clients but does not constrain filesystem access. Tools exposed over `sse` and `stdio` require explicit runtime argument confinement.
