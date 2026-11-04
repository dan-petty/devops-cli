# Proposal

## Why

#3300 reports that the `ops` role publishes 60 tools whose path-like text parameters a model sets, and that SECURITY.md rule 11 requires removal or confinement for every path that a command reads or writes. #3236 planned the confinement tables and audited the job roles, but that plan is not built: `src/devops_cli/ai/mcp/path_confinement.py` does not exist on `main`, and the generated tools pass a model value to the command unchanged. This change delivers the whole class in one pull request: it adds the tables, confines each kept path parameter to the work tree of the server process, removes the two output options that the server can choose, and audits every tool that the server publishes, the `ops` role included.

The plan of #3236 is folded into this change because its tables and its guard are the prerequisite of the full audit. The active folder `openspec/changes/3236-read-only-tools-take-paths-that/` leaves the tree in the same pull request.

## What Changes

- A new module `src/devops_cli/ai/mcp/path_confinement.py` holds `PATH_CONFINEMENTS`, the tool name and the path parameters that the guard confines, and `NOT_A_FILE_PATH`, the tool name and the parameter whose name looks like a path but that is not a file path, with a reason. It also holds `audit_path_parameters(tools)`, which returns one problem for each unconfined path-like parameter, each short reason and each entry that matches no published parameter.
- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gains an entry for `("ai", "ast", "graph")` and one for `("k8s", "security-stream")`. The `output_path` option of the first and the `output` option of the second leave the published schema. The commands print their result, so the model needs no file.
- `_create_tool_function` calls a new `_check_path_confinement` before the command starts. It resolves each kept path argument through `safe_resolve_subpath` against the work tree of the server process, writes the resolved value back, and refuses an escape with a `ValidationError` that names the parameter. The root comes from the process and never from an argument.
- The native `scan_uv_audit` tool confines its `directory` parameter with the same helper.
- A new test `tests/ai/mcp/test_path_confinement.py` audits the published schema of every tool of the `ops` role, which is the whole catalogue, and fails with the tool and parameter name when a path-like parameter has no entry. It also tests that a synthetic tool with an unconfined `output_path` fails, that a short or stale reason fails, that an escape is refused, and that a relative path resolves under the work tree.
- `docs/MCP_TOOLS.md` and the generated command documents are regenerated.
- The change carries a spec delta for the `mcp-tool-path-confinement` capability, because the published schema and the tool behavior are observable to a consumer.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `mcp-tool-path-confinement`: every published path-like parameter of every tool is removed, confined under a server root, or recorded as not a file path with a reason.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/path_confinement.py` (new), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/lang/en/errors.py`
- Documents: `docs/MCP_TOOLS.md`, `docs/ERRORS.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/ai/mcp/test_path_confinement.py` (new), `tests/ai/mcp/test_fastmcp_contracts.py`
- Plans: `openspec/changes/3300-the-ops-role-publishes-60-tools-with/` (new), `openspec/changes/3236-read-only-tools-take-paths-that/` (removed, folded into this change)
- It deletes no internal code beyond the folded plan folder.

## Feasibility

- `git cat-file -e origin/main:src/devops_cli/ai/mcp/path_confinement.py` fails, and `git log --all -- src/devops_cli/ai/mcp/path_confinement.py` prints no commit. #3236 is still an active change with no code, so its tables do not exist.
- A script over `CONST_MCP_EXPOSURE_TABLE` applies `_introspect_command_parameters` and matches `_PATH_PARAM_KEYWORDS` from `src/devops_cli/core/paths.py`. It lists 59 tools, among them `ai_ingest_library.output_dir`, `scan_sbom.output_file`, `scan_aibom.output_file`, `tf_apply.plan_file`, `k8s_create_tls_secret.cert_path`, `vault_get.path` and `vault_sync.path`. The count differs from the issue by one tool because `k8s_security_stream.output` does not hold a keyword; this change removes that option as #3236 planned.
- The same script prints the Click default of each parameter: `k8s_create_tls_secret` and `k8s_enable_tls` default to absolute paths under `~/.config/devops-cli`, `ssh audit` and `ssh status` default to `None`, and the scan and Terraform tools default to `.`. The guard reads only the arguments that a caller supplies, so a server default never trips it.
- `safe_resolve_subpath` in `src/devops_cli/core/paths.py` resolves a relative path against a base, refuses `..`, an absolute path outside the base and a symlink escape, and takes `error_cls`. The helper the guard needs exists.
- `tools_for_role(ROLE_OPS, catalogue)` returns every tool but `hydrate_tool_domain` in `src/devops_cli/ai/mcp/roles.py`, so one audit over that role covers the exposure table and the hand-written tools.

## Existing Tool Considered

No open, maintained library confines the path parameters of an MCP server's tools: FastMCP publishes a schema and runs the function, and pydantic validates types, not containment. The change reuses `pathlib`, `safe_resolve_subpath` and the work-tree helper `find_worktree_root` in `src/devops_cli/core/repo.py`. It builds no path library and adds no dependency. The written cost is about 20,000 tokens to build the tables, the guard and the audit, about 5,000 tokens per year to keep and fix them, and two days elapsed.
