# Design

## Decisions

- **Put the path data in `src/devops_cli/ai/mcp/path_confinement.py`: `PATH_CONFINEMENTS` (tool name to kept parameters) and `NOT_A_FILE_PATH` (tool name to a parameter and its reason).**: The audit needs one place to read. A parameter that is a host, a Vault secret path or a container directory then has a recorded reason and no silent exemption.
- **Drop a path option when the command writes it, or when it has a safe configured default; confine the option that the command must keep.** The write options `output_path`, `output_dir`, `output_file` and `output` leave the schema, because a model that chooses where the server writes is the defect. The certificate and SSH key options leave the schema too, because their configured defaults are absolute paths outside the work tree and the command already reads its store. A read path with a useful relative form, such as `target`, `directory`, `repo_path` or `root_dir`, stays and is confined.
- **Check the value and keep what the model sent.** `_check_path_confinement` calls `safe_resolve_subpath` with the work tree of the server process, and the command receives the original value. The process works in that root, so the resolved path and the original path name the same file. The alternative writes an absolute path back and changes every argv that a contract test holds, with no gain to the rule.
- **Take the root from `Path.cwd()` in the server process, never from a tool argument.**: A root that the model gives would move the boundary that confines the model.
- **Call the guard in `_create_tool_function`, beside `_check_oidc_token_reference`, before `_build_command_argv`.** The existing guards of #2638 and #3222 use this pattern. A refusal reaches the caller as a validation error, and no command starts with a path outside the root.
- **Guard the hand-written `scan_uv_audit` tool in `server.py` too.** It is not in `CONST_MCP_EXPOSURE_TABLE`, so the generator never sees it, but the `ops` role publishes it and it takes a directory.
- **Audit every published tool, not only the exposure table.** The catalogue is a superset: it holds the hand-written tools. The test therefore covers the acceptance criterion for `CONST_MCP_EXPOSURE_TABLE` and closes the same risk for a tool that a later edit registers by hand.
- **A `NOT_A_FILE_PATH` entry needs a reason of at least 30 characters, and the audit fails on a stale entry.** A bare allowlist hides why the parameter is safe, and a stale entry hides that its tool changed.
- **Deliver the module and guard that #3236 plans.** #3300 cannot meet its own acceptance criteria without them, and the plan of #3236 cannot land first inside this pull request. This change therefore does the confinement work of #3236 in full, and the audit covers both the job roles and the `ops` role.

## Rejected alternatives

- **Confine an output path under the work tree instead of dropping it.**: A model could overwrite a source file in the tree. The commands print their report or use a configured data directory, so the model needs no output option.
- **Confine the certificate and SSH key options.**: Their defaults are absolute paths in the user configuration, outside the work tree, so a call with no value would fail. Dropping the option leaves the configured store in charge.
- **Exempt every path-like parameter with a comment instead of a table.** A comment cannot fail the test. The table and the reason length make the audit fail.
- **Audit only `CONST_MCP_EXPOSURE_TABLE`.** It leaves `scan_uv_audit` outside the rule, and that is the one hand-written tool with a path parameter.
- **Add an external path library.** It adds a dependency and still needs the MCP classification and the audit. `safe_resolve_subpath` already covers containment.
- **Audit the job roles only, as #3236 planned.** The issue covers the whole `ops` role and 61 tools, so that audit leaves the reported defect open.
