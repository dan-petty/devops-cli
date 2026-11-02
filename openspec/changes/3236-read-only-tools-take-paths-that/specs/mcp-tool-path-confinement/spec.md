## Purpose
Which path options the MCP tools publish, and how each kept path value is confined to a root that the server sets, so a model that calls a tool reaches no path outside the server work tree.

## ADDED Requirements

### Requirement: A tool publishes no path option that the server can choose
A tool MUST publish no path option when the server can choose the path that the command writes or reads.

#### Scenario: The graph tool writes to a server-chosen file
- **WHEN** A caller reads the published schema of the `ai_ast_graph` tool.
- **THEN** The schema holds no `output_path` property, and the command writes its graph under the data directory.

#### Scenario: The stream tool writes no file
- **WHEN** A caller reads the published schema of the `k8s_security_stream` tool.
- **THEN** The schema holds no `output` property, and the tool prints the stream.

### Requirement: A kept path option resolves under a server root
Every path parameter that a tool publishes MUST resolve through `safe_resolve_subpath` against a root that the server sets before the server opens or writes the path.

#### Scenario: A traversal value is refused
- **WHEN** A caller gives `../../etc/passwd` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool returns a validation error that names the parameter, and no command starts.

#### Scenario: A relative value stays in the work tree
- **WHEN** A caller gives `docs` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool resolves the value under the work tree of the server and runs the command with the resolved path.

#### Scenario: The root is not a tool argument
- **WHEN** A caller reads the published schema of a tool that keeps a path parameter.
- **THEN** The schema holds no property for the confinement root.

### Requirement: The schema audit names an unconfined path parameter
A test SHALL read the published schema of every exposed tool and MUST fail when a path-like text parameter has no confinement entry.

#### Scenario: An unconfined path parameter fails the audit
- **WHEN** An exposed tool publishes a text parameter named like a path and the confinement registry does not name it.
- **THEN** The test fails with the tool name and the parameter name.

#### Scenario: Every exposed tool passes the audit
- **WHEN** The test reads the published schema of every tool of `CONST_MCP_EXPOSURE_TABLE`.
- **THEN** The test passes with a confinement entry for each path-like parameter and none for the removed options.
