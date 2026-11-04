# Tasks

## 1. Confine every kept path parameter

Reads: `src/devops_cli/core/paths.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`.
Changes: `tests/ai/mcp/test_path_confinement.py` (new), `src/devops_cli/ai/mcp/path_confinement.py` (new), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/lang/en/errors.py`.

- [x] 1.1 In `tests/ai/mcp/test_path_confinement.py`, assert that `ai_ast_parse` refuses `/etc/passwd` with a `ValidationError` that names `file_path` and starts no command, and that `docs` resolves under the work tree. Verify `uv run devops ci test tests/ai/mcp/test_path_confinement.py` fails on the base
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`
- [x] 1.2 Write `src/devops_cli/ai/mcp/path_confinement.py` with `PATH_CONFINEMENTS` and `NOT_A_FILE_PATH`. Add `_check_path_confinement` in `generator.py`, call it in `_create_tool_function` before the command starts, and confine `scan_uv_audit.directory` in `server.py`. Add the refusal message to `src/devops_cli/lang/en/errors.py`. Verify `uv run devops ci test tests/ai/mcp/test_path_confinement.py` passes
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py`

## 2. Remove the output options and audit the whole catalogue

Reads: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/roles.py`.
Changes: `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/path_confinement.py`.

- [x] 2.1 In `tests/ai/mcp/test_fastmcp_contracts.py`, assert that the schema of `ai_ast_graph` holds no `output_path` and that of `k8s_security_stream` holds no `output`. In `tests/ai/mcp/test_path_confinement.py`, add the audit cases: every path-like parameter of the `ops` role has an entry, a synthetic `output_path` fails, a short reason fails and a stale entry fails. Verify `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_path_confinement.py` fails on the base
  - Verification: `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_path_confinement.py`
- [x] 2.2 Add the two `_PATH_PARAM_RESTRICTIONS` entries and `audit_path_parameters` in `path_confinement.py`. Verify the same command passes
  - Verification: `uv run devops ci test tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_path_confinement.py`

## 3. Regenerate the documents

Reads: `docs/MCP_TOOLS.md`, `docs/ERRORS.md`.
Changes: `docs/MCP_TOOLS.md`, `docs/ERRORS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/*.md`.

- [x] 3.1 Run `uv run devops docs generate --sync-readme`, and verify `uv run devops ci docs` passes
  - Verification: `uv run devops ci docs`

## Criteria

- Every published path-like parameter is removed, confined or recorded as not a file path with a reason.: group 1, group 2
- The audit covers every tool of the `ops` role, and fails on a short reason and a stale entry.: group 2
- The confinement root is the work tree of the server process and is not a tool argument.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
