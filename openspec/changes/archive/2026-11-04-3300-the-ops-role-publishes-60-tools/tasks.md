# Tasks

## 1. Add the confinement module and the guard

Reads: `src/devops_cli/core/paths.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`.
Changes: `src/devops_cli/ai/mcp/path_confinement.py` (new), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/lang/en/errors.py`, `tests/ai/mcp/test_path_confinement.py` (new).

- [x] 1.1 Write `tests/ai/mcp/test_path_confinement.py` cases first: a traversal value of `root_dir` and an absolute value outside the work tree each raise a `ValidationError` that names the parameter and start no command, a relative value runs the command, and the confinement root is not a tool argument.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`
- [x] 1.2 Write `src/devops_cli/ai/mcp/path_confinement.py` with `PATH_CONFINEMENTS`, `NOT_A_FILE_PATH` and `confine_tool_paths`, which resolves each kept value with `safe_resolve_subpath` against `find_worktree_root(Path.cwd())` and replaces the argument. Add `ERRORS.mcp.path_outside_root`. Call `_check_path_confinement` in `_create_tool_function` before `_build_command_argv`, and call the same check in the hand-written `scan_uv_audit` tool.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`

## 2. Decide every published path parameter

Reads: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/path_confinement.py`.
Changes: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/path_confinement.py`, `tests/ai/mcp/test_path_confinement.py`.

- [x] 2.1 Add `_PATH_PARAM_RESTRICTIONS` entries that drop the write options and the certificate, SSH key and template options that the command replaces with its configured store, in `src/devops_cli/ai/mcp/generator.py`.
  - Verification: `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py`
- [x] 2.2 Record every kept path parameter in `PATH_CONFINEMENTS` and every path-like value that is not a file path in `NOT_A_FILE_PATH`, with a reason of at least 30 characters.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`

## 3. Audit every published tool

Reads: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/core/paths.py`.
Changes: `tests/ai/mcp/test_path_confinement.py`.

- [x] 3.1 Read the published schema of every tool that the server offers, match each text parameter against `_PATH_PARAM_KEYWORDS`, and fail with the tool and parameter name when neither table names it. Fail also on a stale entry and on a reason shorter than 30 characters.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`

## 4. Document the published options

Reads: `docs/MCP_TOOLS.md`.
Changes: `docs/MCP_TOOLS.md`.

- [x] 4.1 Run `uv run devops docs generate --sync-readme`, so the dropped options leave the published schemas in the document.
  - Verification: `uv run devops ci docs`

## Criteria

- No tool publishes a path option that the command writes.: group 2
- Every kept path parameter is confined to the server work tree.: group 1, group 2
- The audit names a published path-like parameter that neither table decides.: group 3
- Each exemption holds a reason of at least 30 characters, and a stale entry fails the audit.: group 3
- `vault_get.path` and `vault_sync.path` are Vault secret paths and not file paths.: group 2
- The listed write tools publish no unconfined write-path option.: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
