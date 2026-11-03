# Design

## Decisions

- **Keep `_PATH_PARAM_RESTRICTIONS` as the only place that decides which options a tool publishes.**: SECURITY.md rule 11 names it as the schema gate, and `generate_mcp_tools` builds every published schema from it.
- **Put the confinement data in a new `src/devops_cli/ai/mcp/path_confinement.py`: `PATH_CONFINEMENTS` (tool name to the parameters that it confines) and `NOT_A_FILE_PATH` (tool name to a parameter with its reason).**: The audit needs one place to read. A parameter that is a host and not a file, such as `target` of `security_intel_network`, then has a recorded reason and no silent exemption.
- **Remove `output_path` from `ai_ast_graph` and `output` from `k8s_security_stream`. Keep `target_dir` of `ai_ast_graph` and `root_dir` of `gh_pages_verify`, confined under the work tree.**: Both commands print their result when no file is given, so the model needs no output option. The two directory options select what the command reads, and a relative path under the work tree is useful.
- **Confine in `_check_path_confinement`, called in `_create_tool_function` beside `_check_oidc_token_reference`, before `_build_command_argv`.**: The existing guards of #2638 and #3222 use this pattern. A refusal reaches the caller as a validation error, and no command starts with a path outside the root.
- **Resolve the root from the work tree of the server process, never from a tool argument.**: A root that a model gives would move the boundary that confines the model.
- **The audit reads the tools of every job role through `tools_for_role`, matches a text parameter whose name holds a keyword of `_PATH_PARAM_KEYWORDS`, and requires an entry in one of the two tables.**: The issue asks for the role tools. A person who adds a tool name to a role table gets a failing test that names the tool and the parameter.
- **Do not audit the `ops` role in this change.**: The census in Feasibility shows 60 tools with a path-like parameter. A test over them needs a decision for each one, and that work is a separate item. The `ops` role is never served over the network.

## Rejected alternatives

- **Leave the path options as they are and rely on the read-only annotation.**: `generate_mcp_tools` sets `annotations={"readOnlyHint": read_only}` and nothing else checks the argument, so a model value reaches the command unchanged.
- **Drop every path option, including `target_dir` and `root_dir`.**: `safe_resolve_subpath` already confines a path under a base with `resolved.is_relative_to(base)`, so a kept option is confined without losing the use of the command.
- **Audit the whole exposure table in this change.**: `tools_for_role("ops", ...)` holds 60 tools with a path-like parameter. One pull request cannot decide them all, and a test with a long exempt list hides the defect that it should show.
- **Add the path tables to `src/devops_cli/ai/mcp/roles.py`.**: That file decides which tools a role holds, and the path decision is about a parameter. Mixing them makes `roles.py` own two reasons to change.
