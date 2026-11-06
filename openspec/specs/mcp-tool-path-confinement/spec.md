# mcp-tool-path-confinement Specification

## Purpose
Which path options an MCP tool publishes, and how each kept path value is confined to the work tree of the server, so a model that calls a tool reaches no path outside the server tree. The audit covers every published tool, including the `ops` role and the hand-written tools.

## Requirements

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

### Requirement: The audit finds a path option by its type
The path-parameter audit SHALL find a published parameter that holds a path by its type and by its name. A command option that Typer reads from a `Path` annotation, or from a file annotation such as `FileText`, SHALL need an entry in `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH` under any name. A parameter of a hand-written tool that carries a `Path` annotation SHALL need one too.

#### Scenario: A path option under a name with no keyword
- **WHEN** The audit reads a tool whose command has a `Path` option named `thing`, and neither table names it.
- **THEN** The audit reports `probe.thing` as a parameter with no decision.

#### Scenario: A file option under a name with no keyword
- **WHEN** The audit reads a tool whose command has a `FileText` option named `thing`, and neither table names it.
- **THEN** The audit reports `probe.thing` as a parameter with no decision.

#### Scenario: A path annotation of a tool that no command backs
- **WHEN** The audit reads a hand-written tool with a `Path` parameter named `thing`, and neither table names it.
- **THEN** The audit reports `probe.thing` as a parameter with no decision.

#### Scenario: A text option with no keyword
- **WHEN** The audit reads a tool whose command has a `str` option named `thing`.
- **THEN** The audit reports nothing, because a type check cannot find a string that holds a path.

#### Scenario: The published catalogue
- **WHEN** The audit reads every tool that the server publishes.
- **THEN** Every published path parameter has an entry in `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH`, among them `ai_harness_offload.repo`, `ai_read.repo`, `docker_sandbox.workspace`, `sandbox_deploy.workspace`, `k8s_diff_helm.values`, `roadmap_refine.source` and `scan_injection.suppress`.

### Requirement: A kept path option refuses a value outside the work tree
The tools `ai_harness_offload`, `ai_read`, `docker_sandbox`, `sandbox_deploy`, `k8s_diff_helm`, `roadmap_refine`, `scan_injection` and `scan_sast` SHALL confine the options `repo`, `repo`, `workspace`, `workspace`, `values`, `source`, `suppress` and `config` respectively under the work tree of the server process. Each tool SHALL refuse a value that escapes the tree with a validation error that names the option, before any command starts.

#### Scenario: A traversal value
- **WHEN** A caller gives `../../etc/passwd` to one of these options.
- **THEN** The tool raises a validation error that names the option, and no command starts.

### Requirement: A sandbox workspace is confined before the sandbox check
The tools `docker_sandbox` and `sandbox_deploy` SHALL confine `workspace` under the work tree first. They SHALL then run `validate_sandbox_workspace` on the resolved value.

#### Scenario: A workspace outside the work tree
- **WHEN** A caller gives an absolute directory outside the work tree to `workspace`, and the directory is no forbidden root.
- **THEN** The tool raises a validation error that names `workspace`, and no command starts.

#### Scenario: A sensitive directory inside the work tree
- **WHEN** A caller gives `.ssh` inside the work tree to the `workspace` of `docker_sandbox`.
- **THEN** The tool raises a sandbox validation error, and no command starts.

### Requirement: A text option that holds a path has a named decision
The option `config` of `scan_sast` SHALL have an entry in `PATH_CONFINEMENTS` and an entry in `NOT_A_PATH_VALUE`. A value that is a Semgrep registry id SHALL reach the command unchanged. Any other value SHALL resolve under the work tree before the command gets it.

#### Scenario: A registry id
- **WHEN** A caller gives `p/python` to `config`, or gives no config.
- **THEN** The command gets `p/python`, or the default `p/default`, as it is.

#### Scenario: A local path
- **WHEN** A caller gives `rules` to `config`.
- **THEN** The command gets the absolute path of `rules` under the work tree.

#### Scenario: A URL
- **WHEN** A caller gives `https://example.com/rules.yaml` to `config`.
- **THEN** The command gets a path under the work tree, and not the URL.

### Requirement: An option that writes the feedback dataset is not published
The tool `review_export_feedback` SHALL publish no `output` option. The command `devops review export-feedback` SHALL keep the option `--output`.

#### Scenario: The published tool
- **WHEN** A test reads the published schema of `review_export_feedback`.
- **THEN** The schema holds `reviews_dir`, `status` and `dry_run`, and no `output`.

#### Scenario: The command
- **WHEN** A test reads the options of `devops review export-feedback`.
- **THEN** The options include `--output`.

### Requirement: The runtime path check keeps its keywords
`validate_path_parameter` SHALL refuse a `..` value for each parameter whose name holds a word of `_PATH_PARAM_KEYWORDS`. It SHALL read none of the names `repo`, `workspace`, `values`, `source`, `suppress` and `config` as a path name.

#### Scenario: A keyword name
- **WHEN** `validate_path_parameter` gets the value `../x` for a parameter named `my_` and one of the keywords.
- **THEN** It raises a security error.

#### Scenario: A name with no keyword
- **WHEN** `validate_path_parameter` gets the value `../x` for `repo`, `workspace`, `values`, `source`, `suppress` or `config`.
- **THEN** It raises nothing.
