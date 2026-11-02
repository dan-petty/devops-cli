# Design

## Decisions

- **Keep one registry, `_PATH_PARAM_RESTRICTIONS`, as the only place that decides which options a tool publishes.**: SECURITY.md rule 11 names it as the schema gate, and `generate_mcp_tools` already builds every published schema from it.
- **Put the confinement entry of each kept path parameter in a new `PATH_CONFINEMENTS` mapping in `src/devops_cli/ai/mcp/path_confinement.py`, keyed by command path and parameter name, with the server root that confines it.**: The generator holds the publish decision, and the confinement needs a root and a helper. A separate mapping gives the schema audit one place to read.
- **Remove `output_path` from `ai_ast_graph` and `output` from `k8s_security_stream`, and keep `root_dir` of `gh_pages_verify` confined under the work tree.**: The server can choose the output location of the first two, so the model needs no option. `gh_pages_verify` must read the tree that the server names, and a relative path under the work tree is useful.
- **Confine each kept path argument inside the tool function, before `_build_command_argv` runs.**: A refusal then reaches the caller as a validation error of the tool, and no command starts with a path outside the root.
- **Resolve the server root from the settings data directory and the work tree of the server process, never from a tool argument.**: A root that a model gives would move the boundary that confines the model.
- **The schema audit reads every tool of `CONST_MCP_EXPOSURE_TABLE`, matches a text parameter whose name holds a path keyword, and requires a confinement entry.**: It covers every current tool and every tool added to the table later, and it names the tool and the parameter when it fails.

## Rejected alternatives

- **Leave the path options as they are and rely on the read-only annotation.**: `generate_mcp_tools` sets `annotations={"readOnlyHint": read_only}` and nothing else checks the argument, and `_PATH_PARAM_RESTRICTIONS` holds no entry for the three commands, so a model value reaches the command unchanged.
- **Drop every path option, including `root_dir` of `gh_pages_verify`.**: `safe_resolve_subpath` in `src/devops_cli/core/paths.py` already confines a path under a base with the check `if not resolved.is_relative_to(base)`, so a kept option is confined without losing the command's use.
- **Add a second registry in a role-table module.**: `src/devops_cli/ai/mcp/roles.py` is no file of the staging commit, and `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is already the table that the published schema comes from.
- **Audit only the three example tools.**: `generate_mcp_tools` loops over `CONST_MCP_EXPOSURE_TABLE`, so a tool added to that table would escape a hard-coded check.
