# Proposal

## Why

Some MCP tools that the exposure table marks read-only publish a path parameter (`ai_ast_graph` publishes `target_dir` and `output_path`, `k8s_security_stream` publishes `output`, `gh_pages_verify` publishes `root_dir`). The model that calls the tool chooses the value. Without confinement, the server opens or writes a path outside its work tree or data directory. SECURITY.md rule 11 requires a path helper to confine a path that a model gives. #3236 asks for path confinement and for an audit that detects unconfined path parameters.

## What Changes

- Extend `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` to record path confinement rules and allowed parameter sets for exposed commands.
- `("ai", "ast", "graph")` publishes no `output_path` property because the command prints to standard output when `--output` is omitted; `target_dir` is kept and confined to the repository root.
- `("k8s", "security-stream")` publishes no `output` property because the tool prints security events to standard output without writing files.
- `("gh", "pages", "verify")` keeps `root_dir` (CLI flag `--dir`) and confines it to the repository root.
- The tool generator function in `src/devops_cli/ai/mcp/generator.py` resolves kept path arguments against the server root and sanitizes traversal error messages to omit internal server paths.
- Add `CONST_MCP_PATH_PARAMETER_ALLOWLIST` in `src/devops_cli/config/constants.py` with explicit reasons of at least 30 characters for non-file text parameters matching path keywords.
- Add `tests/ai/mcp/test_path_confinement.py` to audit the published schema of exposed tools against `CONST_MCP_PATH_PARAMETER_ALLOWLIST` and check for stale allow-list entries.
- Add a test in `tests/ai/mcp/test_mcp_roles.py` verifying that no job role tool exposes an unconfined path parameter.
- Update `SECURITY.md` rule 11 to cite `_PATH_PARAM_RESTRICTIONS` confinement and `tests/ai/mcp/test_path_confinement.py`.
- Regenerate documentation via `uv run devops docs generate --sync-readme`.
- The change fits one pull request.

## Order and Dependencies

- Depends on merged changes #3219 and #3233 (both present on `main`).
- Related open items: #3235 (updates read-only flags of `CONST_MCP_EXPOSURE_TABLE`), #3220, and #3221 (consumers of MCP server endpoints).

## Capabilities

### New Capabilities

- `mcp-tool-path-confinement`: A tool publishes no path option that the server can choose, A kept path option resolves under a server root, The schema audit names an unconfined path parameter

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/constants.py`, `SECURITY.md`.
- Documents: `docs/MCP_TOOLS.md` (regenerated via CLI).
- Tests: `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp.py`, `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_mcp_roles.py`.

## Feasibility

- `src/devops_cli/ai/mcp/generator.py` defines `_PATH_PARAM_RESTRICTIONS`. It holds no entry for `("ai", "ast", "graph")`, `("gh", "pages", "verify")`, or `("k8s", "security-stream")`. Therefore all CLI options publish as tool parameters.
- `src/devops_cli/commands/ai_ast.py:113-122` shows that `ai_ast_graph` prints to stdout when `--output` is omitted: `if output_path: output_path.write_text(...) else: write_stdout(content + "\n")`. It also accepts `target_dir: Annotated[Path | None, typer.Option("--dir", "-d")] = None`.
- `src/devops_cli/commands/gh.py:1136-1141` shows that `pages_verify_cmd` accepts `root_dir: Annotated[Path, typer.Option("--dir", "-d")] = Path(".")`.
- `src/devops_cli/commands/k8s/diagnostics.py:398-400` shows that `security_stream_cmd` accepts `output: Annotated[Path | None, typer.Option("--output", "-o")] = None`.
- `src/devops_cli/core/paths.py:35` provides `safe_resolve_subpath`. The error message on line 83 contains the base path: `f"Path traversal detected: path '{subpath}' escapes base directory '{base}'."`. The tool wrapper must sanitize this error to avoid leaking internal server paths.
- `src/devops_cli/ai/mcp/roles.py` defines `_JOB_ROLE_TOOLS` for `ROLE_PLANNING`, `ROLE_IMPLEMENTATION`, and `ROLE_REVIEW`. Role tools hold only `security_intel_network.target`, which represents a network host rather than a file path. Confinement protects `sse` and `stdio` transports where the full catalogue is exposed.
- Commands verified against the real system:
  `uv run devops ai ast graph --help` prints the valid options for the graph command.
  `uv run devops gh pages verify --help` shows option `--dir` (`-d`).
  `uv run devops k8s security-stream --help` shows option `--output` (`-o`).

## Existing Tool Considered

No open, maintained library confines the path parameters of FastMCP tools. FastMCP publishes a tool schema and executes tool functions, while Pydantic validates types rather than containment. The change reuses `safe_resolve_subpath` in `src/devops_cli/core/paths.py` and extends `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py`. The written cost is approximately 12,000 tokens to build, 3,000 tokens per year to maintain, and one day elapsed. No tool function or existing registry entry is deleted.
