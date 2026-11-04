# mcp-tool-path-confinement Specification

## Purpose
Which path options the MCP tools publish, and how each kept path value is confined to a root that the server sets, so a model that calls a tool reaches no path outside the server work tree. The audit covers every published tool, the `ops` role included.

## Requirements

### Requirement: A tool publishes no path option that the server can choose
A tool MUST publish no path option when the server can choose the path that the command writes or reads.

#### Scenario: The graph tool prints its graph
- **WHEN** A caller reads the published schema of the `ai_ast_graph` tool.
- **THEN** The schema holds no `output_path` property, and the command prints its graph.

#### Scenario: The stream tool writes no file
- **WHEN** A caller reads the published schema of the `k8s_security_stream` tool.
- **THEN** The schema holds no `output` property, and the tool prints the stream.

### Requirement: A kept path option resolves under a server root
Every path parameter that a tool publishes MUST resolve through `safe_resolve_subpath` against a root that the server sets before the server opens or writes the path.

#### Scenario: A traversal value is refused
- **WHEN** A caller gives `../../etc/passwd` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool returns a validation error that names the parameter, and no command starts.

#### Scenario: A directory of the graph tool is confined
- **WHEN** A caller gives `/etc` to the `target_dir` parameter of `ai_ast_graph`.
- **THEN** The tool returns a validation error that names the parameter, and no command starts.

#### Scenario: A relative value stays in the work tree
- **WHEN** A caller gives `docs` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool resolves the value under the work tree of the server and runs the command with the resolved path.

#### Scenario: The root is not a tool argument
- **WHEN** A caller reads the published schema of a tool that keeps a path parameter.
- **THEN** The schema holds no property for the confinement root.

### Requirement: Write path confinement
Every MCP tool that writes a file SHALL remove each path parameter from its schema or SHALL confine it with `PATH_CONFINEMENTS`.

#### Scenario: Unconfined write path
- **WHEN** A tool publishes a write-path parameter that matches `_PATH_PARAM_KEYWORDS`.
- **THEN** The audit fails unless the parameter has a `PATH_CONFINEMENTS` entry.

#### Scenario: Listed write tool schema
- **WHEN** The test reads the published schema of each listed write tool.
- **THEN** Each path-like write parameter is absent or has a `PATH_CONFINEMENTS` entry.

### Requirement: Read path confinement
Every MCP tool that reads a file SHALL remove each path parameter from its schema or SHALL confine it with `PATH_CONFINEMENTS`.

#### Scenario: Unconfined read path
- **WHEN** A tool publishes a read-path parameter that matches `_PATH_PARAM_KEYWORDS`.
- **THEN** The audit fails unless the parameter has a `PATH_CONFINEMENTS` entry.

### Requirement: Full exposure audit
The path-parameter audit SHALL inspect every tool that the `ops` role publishes, including a tool outside the job roles.

#### Scenario: Tool outside the job roles
- **WHEN** A tool that the `ops` role publishes is not in a job role and publishes a path-like parameter.
- **THEN** The audit checks that parameter and fails when no entry exists.

#### Scenario: Synthetic unconfined tool
- **WHEN** The audit reads a synthetic tool with an `output_path` property.
- **THEN** The audit returns one problem that names the tool and the parameter.

### Requirement: Reasoned non-file exemption
Each `NOT_A_FILE_PATH` entry SHALL hold a reason of at least 30 characters, and the audit MUST fail on a missing or short reason.

#### Scenario: Bare or short exemption
- **WHEN** A path-like parameter has a `NOT_A_FILE_PATH` entry with no reason or a reason shorter than 30 characters.
- **THEN** The audit fails and names the tool and parameter.

### Requirement: Stale exemption
The audit MUST fail when a `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH` entry names no published path-like parameter.

#### Scenario: Stale non-file entry
- **WHEN** An entry matches no published parameter.
- **THEN** The audit fails and names the stale entry.

### Requirement: Vault secret paths
The `vault_get.path` and `vault_sync.path` parameters SHALL be recorded in `NOT_A_FILE_PATH` as Vault secret paths, not filesystem paths.

#### Scenario: Vault path exemption
- **WHEN** The audit reads `vault_get.path` or `vault_sync.path`.
- **THEN** The audit accepts the parameter only through its `NOT_A_FILE_PATH` reason and not through a filesystem confinement.
