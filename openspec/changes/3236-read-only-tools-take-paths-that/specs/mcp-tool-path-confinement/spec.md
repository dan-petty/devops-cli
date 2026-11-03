## Purpose
Define which path options MCP tools publish and how kept path parameters are confined to server-defined roots, so that a model cannot access or write files outside authorized boundaries.

## ADDED Requirements

### Requirement: A tool publishes no path option that the server can choose
A tool MUST NOT publish a path option when the command can execute with default server-side output handling.

#### Scenario: The graph tool publishes no output path and confines target directory
- **WHEN** A caller inspects the published schema of `ai_ast_graph`.
- **THEN** The schema does not contain an `output_path` property, and `target_dir` is confined to the repository root.

#### Scenario: The security stream tool publishes no output path
- **WHEN** A caller inspects the published schema of `k8s_security_stream`.
- **THEN** The schema does not contain an `output` property, and the tool streams events to standard output.

### Requirement: A kept path option resolves under a server root
Every path parameter published by a tool MUST resolve through `safe_resolve_subpath` against the designated server root before command execution.

#### Scenario: A path traversal value is rejected without server path leakage
- **WHEN** A caller supplies `../../etc/passwd` to `root_dir` on `gh_pages_verify`.
- **THEN** The tool raises a validation error naming the parameter, and the error message does not disclose the absolute server root path.

#### Scenario: A relative path value resolves within the repository root
- **WHEN** A caller supplies `docs` to `root_dir` on `gh_pages_verify`.
- **THEN** The tool resolves the path under the repository root and executes the command with the resolved path.

#### Scenario: The confinement root is not a tool parameter
- **WHEN** A caller inspects the published schema of any tool with confined parameters.
- **THEN** The schema does not publish a parameter for the confinement root directory.

### Requirement: Schema audits verify parameter confinement and role boundaries
Tests MUST verify that all exposed tools with path-like parameters have valid confinement or allow-list entries, and that job roles contain no unconfined path parameters.

#### Scenario: Exposed catalogue path parameters match confinement or allow-list entries
- **WHEN** The audit inspects all text parameters matching path keywords across tools from `mcp._list_tools()`.
- **THEN** Every parameter has either a confinement rule in `_PATH_PARAM_RESTRICTIONS` or an entry in `CONST_MCP_PATH_PARAMETER_ALLOWLIST` with an explanatory reason of at least 30 characters.

#### Scenario: Job role tools contain no unconfined file path parameters
- **WHEN** The role audit inspects all tools registered in `_JOB_ROLE_TOOLS`.
- **THEN** No tool exposes an unconfined file path parameter.
