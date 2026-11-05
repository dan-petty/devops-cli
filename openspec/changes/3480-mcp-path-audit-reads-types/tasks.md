# Tasks

## 1. Find a path option by its type and decide each option

Kind: behavior. Reads: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/sandbox/engine.py` (`validate_sandbox_workspace`), `src/devops_cli/core/paths.py` (`validate_path_parameter`), `tests/ai/mcp/test_mcp_read_only_write_options.py`. Changes: `tests/ai/mcp/test_path_confinement.py`, `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_mcp.py`, `tests/commands/test_sandbox_lifecycle.py`.

- [x] 1.1 In `tests/ai/mcp/test_path_confinement.py`, make the audit read the type and the name of each published parameter. A tool of the exposure table gives the Click type (`typer.models.TyperPath`). A tool that no command backs gives `format: path`. The test table `_TEXT_PATH_OPTIONS` names `scan_sast.config`. Add the cases of the spec: a fixture tool with a `Path` option, and one with a `FileText` option, under a name with no keyword fails the audit. The published catalogue passes it, and each option of the census has a decision or is not published. A traversal value of each of the eight options is refused before a command runs. Both sandbox tools refuse a workspace outside the work tree, and the sandbox check still refuses `.ssh` inside it. The Semgrep config keeps a registry id and confines a path and a URL. `review_export_feedback` publishes no `output`. The runtime keyword check keeps its words.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py` fails on the base
- [x] 1.2 In `src/devops_cli/ai/mcp/path_confinement.py`, add the eight entries to `PATH_CONFINEMENTS` and the table `NOT_A_PATH_VALUE` with the Semgrep registry id test, and skip such a value in `confine_tool_paths`. In `src/devops_cli/ai/mcp/generator.py`, add the `("review", "export-feedback")` entry to `_PATH_PARAM_RESTRICTIONS`, and call `_check_path_confinement` before `_check_sandbox_preconditions`. Give the five tests that passed a path outside the tree, or a relative path, a work tree with `monkeypatch.chdir(tmp_path)`: three in `tests/ai/mcp` and two in `tests/commands/test_sandbox_lifecycle.py`. Remove the `run-user` case from the sandbox tool test, because confinement refuses it first.
  - Verification: `uv run devops ci test tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_mcp.py tests/ai/mcp/test_mcp_read_only_write_options.py tests/commands/test_sandbox_lifecycle.py` passes

## 2. Regenerate the MCP tool reference

Kind: documentation. Reads: `docs/MCP_TOOLS.md`. Changes: `docs/MCP_TOOLS.md` (generated).

- [x] 2.1 Run `uv run devops docs generate --sync-readme`. Only the `output` row of `review_export_feedback` in `docs/MCP_TOOLS.md` goes.
  - Verification: `uv run devops ci docs` passes

## Criteria

- The audit finds a path option by its type: group 1
- A kept path option refuses a value outside the work tree: group 1
- A sandbox workspace is confined before the sandbox check: group 1
- A text option that holds a path has a named decision: group 1
- An option that writes the feedback dataset is not published: group 1
- The runtime path check keeps its keywords: group 1
- The MCP Semgrep tool uses the default ruleset unless the caller names one: group 1

## Workflow follow-up

- Issue #3642 owns the read-only flag of the tools that write local state, among them `review_export_feedback`.
- Issue #3230 plans a table of free-text parameters that can carry a secret, with an entry for `k8s_diff_helm.values`. That table decides a secret and not a path, so it does not replace the decision of this change.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
