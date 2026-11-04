## ADDED Requirements

### Requirement: Write path confinement
Every MCP tool that writes a file MUST remove each path parameter from its published schema or SHALL confine it with `PATH_CONFINEMENTS`.

#### Scenario: Unconfined write path
- **WHEN** A tool in the catalogue publishes a write-path parameter that matches `_PATH_PARAM_KEYWORDS`.
- **THEN** The audit fails unless the parameter has a `PATH_CONFINEMENTS` entry.

#### Scenario: Listed write tools publish no write path
- **WHEN** A caller reads the published schema of `ai_ingest_library`, `scan_sbom`, `scan_aibom`, `tf_apply` or `k8s_create_tls_secret`.
- **THEN** Each path-like write parameter is absent or has a `PATH_CONFINEMENTS` entry.

### Requirement: Read path confinement
Every MCP tool that reads a file MUST remove each path parameter from its published schema or SHALL confine it with `PATH_CONFINEMENTS`.

#### Scenario: Unconfined read path
- **WHEN** A tool in the catalogue publishes a read-path parameter that matches `_PATH_PARAM_KEYWORDS`.
- **THEN** The audit fails unless the parameter has a `PATH_CONFINEMENTS` entry.

#### Scenario: A traversal value is refused
- **WHEN** A caller gives `../../etc/passwd` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool raises a validation error that names the parameter, and no command starts.

#### Scenario: A relative value stays in the work tree
- **WHEN** A caller gives `docs` to the `root_dir` parameter of `gh_pages_verify`.
- **THEN** The tool resolves the value under the work tree of the server and runs the command with the resolved path.

### Requirement: Full catalogue audit
The path-parameter audit SHALL inspect every tool that the server offers, including the hand-written tools and the `ops` role.

#### Scenario: Tool outside the exposure table
- **WHEN** A hand-written tool such as `scan_uv_audit` publishes a path-like parameter.
- **THEN** The audit checks that parameter and fails when no entry exists.

#### Scenario: Tool outside the job roles
- **WHEN** A tool in `CONST_MCP_EXPOSURE_TABLE` is not in a job role and publishes a path-like parameter.
- **THEN** The audit checks that parameter and fails when no entry exists.

### Requirement: Reasoned non-file exemption
Each `NOT_A_FILE_PATH` entry SHALL hold a reason of at least 30 characters, and the audit MUST fail on a missing or short reason.

#### Scenario: Bare or short exemption
- **WHEN** A path-like parameter has a `NOT_A_FILE_PATH` entry with no reason or a reason shorter than 30 characters.
- **THEN** The audit fails and names the tool and parameter.

### Requirement: Stale exemption
The audit MUST fail when a `NOT_A_FILE_PATH` entry names no published path-like parameter.

#### Scenario: Stale non-file entry
- **WHEN** A `NOT_A_FILE_PATH` entry matches no published parameter.
- **THEN** The audit fails and names the stale entry.

### Requirement: Vault secret paths
The `vault_get.path` and `vault_sync.path` parameters SHALL be recorded in `NOT_A_FILE_PATH` as Vault secret paths, not filesystem paths.

#### Scenario: Vault path exemption
- **WHEN** The audit reads `vault_get.path` or `vault_sync.path`.
- **THEN** The audit accepts the parameter only through its `NOT_A_FILE_PATH` reason and not through a filesystem confinement.
