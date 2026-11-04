# Proposal

## Why

The `ops` role holds every MCP tool, and 61 of them publish 70 text parameters with a path-like name that the server opens or writes (#3300). SECURITY.md rule 11 says a tool publishes no option for a path that the command reads or writes, unless a path helper confines it. The confinement tables and the guard that #3236 plans do not exist on `main` yet. This change adds them, decides every published path parameter, and audits the whole catalogue, so a new tool cannot escape the rule in silence.

## What Changes

- A new module `src/devops_cli/ai/mcp/path_confinement.py` holds `PATH_CONFINEMENTS`, which names each kept path parameter of a tool, and `NOT_A_FILE_PATH`, which names each text parameter whose name looks like a path and that the command does not open, with a reason of at least 30 characters.
- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` drops each path option that the model must not choose. The write paths come first: `ai_ast_graph.output_path`, `ai_ingest_library.output_dir`, `scan_sbom.output_file`, `scan_aibom.output_file` and `k8s_security_stream.output`. The change also drops the certificate options of `k8s_create_tls_secret` and `k8s_enable_tls` and the SSH key directory, so each command reads its configured store.
- `_check_path_confinement` in `generator.py` runs in `_create_tool_function` beside the other guards, before the command starts. It checks each kept path value with `safe_resolve_subpath` against the work tree of the server process and refuses an escape with a `ValidationError` that names the parameter. The same check guards the hand-written `scan_uv_audit` tool in `server.py`.
- A new test `tests/ai/mcp/test_path_confinement.py` reads the published schema of every tool that the server offers, including the hand-written tools, and fails on a text parameter with a path-like name that neither table names. It also fails on a missing or short reason and on a stale entry.
- `docs/MCP_TOOLS.md` is regenerated: the dropped options leave the published schemas.
- The change carries a spec delta for the `mcp-tool-path-confinement` capability, because the published schema and the refusal are observable to a consumer.
- The change fits one pull request.

## Feasibility

- `git show HEAD:src/devops_cli/ai/mcp/path_confinement.py` exits 128, so `main` holds no confinement module. `grep` finds `_PATH_PARAM_RESTRICTIONS` in `generator.py` and `_PATH_PARAM_KEYWORDS` in `core/paths.py`, but no call to `safe_resolve_subpath` in the MCP package.
- A script imports `devops_cli.ai.mcp.server.mcp`, lists each published tool schema and matches `_PATH_PARAM_KEYWORDS`: it finds 70 text parameters in 61 tools, for example `scan_sbom.output_file`, `tf_apply.plan_file`, `ai_read.target_path`, `vault_get.path` and `scan_uv_audit.directory`.
- The same script reads each Click command through `resolve_click_command`: every dropped option is optional, so the command keeps a usable default. The certificate defaults of `k8s_create_tls_secret` and `k8s_enable_tls` are absolute paths in the user configuration, so the change drops those options instead of confining a value outside the work tree.
- `src/devops_cli/core/paths.py` holds `safe_resolve_subpath`, which resolves a relative or absolute path under a base and raises on `..`, on an escape and on a symlink escape. The helper the change needs exists.
- `uv run devops ci test tests/ai/mcp` passes on the base, so the audit starts from a green suite.

## Existing Tool Considered

No open, maintained library confines the path parameters of an MCP server's tools: FastMCP publishes a schema and pydantic validates types, not containment. The change reuses `safe_resolve_subpath` in `src/devops_cli/core/paths.py` and the `_PATH_PARAM_RESTRICTIONS` table of `generator.py`, so it adds no dependency. The written cost of the module, the guard and the audit is about 20,000 tokens to build, about 5,000 tokens per year to keep and fix, and one day elapsed. The change deletes no tool function, registry entry or test. It removes published options only, and the commands keep a configured default for each one.

## Capabilities

### New Capabilities

- `mcp-tool-path-confinement`: A tool publishes no path option that the server can choose, A kept path option is confined to a server root, Every published path-like parameter has a confinement or a reasoned exemption.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/path_confinement.py` (new), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/lang/en/errors.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_path_confinement.py` (new)
