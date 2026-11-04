# Design

## Decisions

- **Fold the unbuilt plan of #3236 into this change.** Its tables and guard are the prerequisite of the full audit, and its active folder would otherwise race the archive of this change for one capability. The folder leaves the tree in this pull request.
- **Keep `_PATH_PARAM_RESTRICTIONS` as the only place that decides which options a tool publishes.** SECURITY.md rule 11 names it as the schema gate, and `generate_mcp_tools` builds every published schema from it.
- **Put the path data in `src/devops_cli/ai/mcp/path_confinement.py`: `PATH_CONFINEMENTS` maps a tool name to the parameters that the guard confines, and `NOT_A_FILE_PATH` maps a tool name to a parameter with its reason.** The audit needs one place to read, and a parameter that is a host or a model name has a recorded reason instead of a silent exemption.
- **Confine every kept file path under the work tree of the server process, never under a path that a model gives.** `safe_resolve_subpath` already refuses `..`, an absolute path outside the base and a symlink escape, so the guard reuses it instead of a new resolver. A caller that omits the option gets the command default, because the guard reads only the arguments that the caller supplies.
- **Remove `output_path` from `ai_ast_graph` and `output` from `k8s_security_stream`.** Both commands print their result when no file is given, so the model needs no output option. Keep `target_dir` of `ai_ast_graph` and `root_dir` of `gh_pages_verify`, confined.
- **Record a parameter that is not a file path in `NOT_A_FILE_PATH` with a reason of at least 30 characters.** `target_provider` and `target_model` name a provider and a model, `max_files` is a count, `file_filter` is a glob, `filed_by` is an enum, and `destroy` is a flag that a keyword matches by substring. `vault_get.path` and `vault_sync.path` name a secret in Vault, not a file.
- **Audit `tools_for_role(ROLE_OPS, catalogue)`, which is every published tool.** The issue covers the whole exposure table, and the hand-written tools share the catalogue, so one audit leaves no tool outside it. The audit fails on an unconfined parameter, a short reason and a stale entry, and names the tool and the parameter.
- **Put the audit in the new module and call it from the test.** The test stays a thin assertion, and a later caller can run the same audit without importing the test.

## Rejected alternatives

- **Leave the path options as they are and rely on the read-only annotation.** `generate_mcp_tools` sets `annotations={"readOnlyHint": read_only}` and nothing else checks the argument, so a model value reaches the command unchanged.
- **Drop every path option, including `target_dir` and `root_dir`.** `safe_resolve_subpath` already confines a path under a base, so a kept option is confined without losing the use of the command.
- **Confine under the home directory or a data directory for the tools that default outside the work tree.** A model could then read every file of the home directory through those tools. The guard checks only supplied arguments, so the command default stays and a model-chosen path stays in the work tree.
- **Audit the exposure table literal only.** `CONST_MCP_EXPOSURE_TABLE` omits the hand-written tools, so `scan_uv_audit.directory` would escape the audit. The catalogue through `tools_for_role(ROLE_OPS, ...)` holds both.
- **A bare exempt list.** A bare entry hides why the parameter is safe and cannot fail the test. A reason of at least 30 characters and the stale check keep the list honest.
