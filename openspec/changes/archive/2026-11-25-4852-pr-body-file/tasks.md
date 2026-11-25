# Tasks

## 1. `--body-file` option and form validation (kind: behavior)

- [x] 1.1 Write failing tests for `--body-file`/`-F`, `-` stdin, mutual exclusion with `--body`, missing-file exit `2`, and `pr create` 1,000-character and template checks
  - Verification: `$ uv run devops ci test tests/commands/test_pr_form_check.py tests/commands/test_pr_cmd.py tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_mcp_tool_listing.py`
- [x] 1.2 Add `_resolve_body_input` and `--body-file`/`-F` to `pr create` and `pr edit` in `src/devops_cli/commands/pr.py`, help text in `src/devops_cli/lang/en/help.py`, `"pr_edit"` in `src/devops_cli/ai/mcp/path_confinement.py`, and update MCP tool snapshot
  - Verification: `$ uv run devops ci test tests/commands/test_pr_form_check.py tests/commands/test_pr_cmd.py tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_mcp_tool_listing.py`

## 2. Generated CLI and MCP docs (kind: documents)

- [x] 2.1 Regenerate documentation via `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`

## 3. Quality gate

- [x] 3.1 Pass `uv run devops ci --check` and OpenSpec checks
  - Verification: `$ uv run devops ci --check`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
