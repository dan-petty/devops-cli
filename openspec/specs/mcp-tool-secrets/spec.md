# mcp-tool-secrets Specification

## Purpose
Defines how the MCP tools of devops-cli treat secret values. The model writes the arguments of a tool call, so a tool publishes no parameter that takes a secret value, never returns a credential, and the run trace hides the value of an argument by its name.

## Requirements

### Requirement: No MCP tool publishes a parameter that takes a secret value
No registered MCP tool SHALL publish a text parameter whose name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS`, unless `CONST_MCP_SECRET_PARAMETER_ALLOWLIST` names the tool and the parameter with a reason. A parameter that cannot hold text (a flag, a number, a fixed choice) SHALL NOT need an entry. The tool `vault_set` SHALL NOT exist. The tool `vault_get` SHALL publish `path`, `key` and `dry_run`, and no other parameter.

#### Scenario: The published schemas
- **WHEN** a test reads the JSON Schema of every registered tool
- **THEN** each text parameter with a secret word in its name is on the allow-list
- **AND** each allow-list entry names a live parameter and a reason of at least 30 characters

#### Scenario: The secret-storing tool
- **WHEN** an MCP client lists the tools of the vault domain
- **THEN** `vault_get`, `vault_status` and `vault_sync` are listed and `vault_set` is not

#### Scenario: The vault reading tool shows no value
- **WHEN** an MCP client reads the schema of `vault_get`
- **THEN** its parameters are `path`, `key` and `dry_run`

### Requirement: The sign tool takes the OIDC token as a keyring reference only
The MCP tool `docker_sign` SHALL accept `oidc_token` only when the value starts with `keyring:`. A call with any other value SHALL fail before any command runs, with an error that names `oidc_token` and does not repeat the value. The reference SHALL go to the command as `--oidc-token keyring:<name>`, and the tool SHALL set no environment variable for the token.

#### Scenario: A token in the argument
- **WHEN** a client calls `docker_sign` with `oidc_token` set to a JSON Web Token
- **THEN** the call fails with an error that names `oidc_token`
- **AND** the error text does not hold the token, and no command runs

#### Scenario: A keyring reference
- **WHEN** a client calls `docker_sign` with `oidc_token` set to `keyring:cosign_oidc`
- **THEN** the command line holds `--oidc-token keyring:cosign_oidc`
- **AND** the call sets no environment variable for the command

### Requirement: The run trace hides an argument by its name
`RunTrace` SHALL replace the value of a tool-call argument with `<redacted>` when the name of the argument holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS`, at any depth of objects and lists, whatever the form of the value. It SHALL mask the rest of the argument text with `mask_secrets` and cut it to the limit of the trace.

#### Scenario: An opaque value under a secret name
- **WHEN** a tool call has the argument `{"path": "/v1/a", "api_key": "opaque-value", "nested": {"password": "hunter2"}}`
- **THEN** the trace argument is `{"path":"/v1/a","api_key":"<redacted>","nested":{"password":"<redacted>"}}`

#### Scenario: An argument that is no JSON object
- **WHEN** a tool call has an argument text that holds a GitHub token and is no JSON object
- **THEN** the trace argument does not hold the token

### Requirement: The sandbox deploy tool publishes no env parameter
The MCP tool `sandbox_deploy` SHALL publish no `env` parameter.

#### Scenario: Published sandbox deploy schema
- **WHEN** A test generates the MCP tools and reads the schema of `sandbox_deploy`.
- **THEN** The schema has no `env` property.

### Requirement: The server publishes no valkey set tool
The MCP server SHALL publish no `valkey_set` tool.

#### Scenario: Published valkey tools
- **WHEN** A test generates the MCP tools and lists their names.
- **THEN** The list holds no `valkey_set` name.

### Requirement: A denied parameter leaves the tool schema
The MCP generator SHALL omit every parameter that the `denied` set of a path restriction names.

#### Scenario: Denied parameter in a path restriction
- **WHEN** A test gives a path restriction a `denied` set that holds `env`, and the command publishes an `env` option.
- **THEN** The generated tool schema has no `env` property.

### Requirement: A free-text sink parameter needs an allow-list entry
The MCP schema guard SHALL fail on a published text parameter named `env`, `values`, `value` or `data` that has no allow-list entry with a reason.

#### Scenario: Unallowed free-text sink parameter
- **WHEN** A test registers a tool that publishes a text parameter named `value`, and the allow-list holds no entry for it.
- **THEN** The guard fails and names the tool and the parameter.

#### Scenario: Allowed free-text sink parameter
- **WHEN** A test registers a tool that publishes a text parameter named `data`, and the allow-list holds an entry for the tool and the parameter with a reason.
- **THEN** The guard passes.

### Requirement: A free-text allow-list entry names a published parameter
The MCP schema guard SHALL fail on an allow-list entry that matches no published parameter.

#### Scenario: Stale free-text allow-list entry
- **WHEN** The allow-list holds an entry for a tool and parameter that the server does not publish.
- **THEN** The guard fails and names the stale entry.

#### Scenario: Live free-text allow-list entry
- **WHEN** The allow-list holds an entry for `k8s_diff_helm.values` and the server publishes `k8s_diff_helm`.
- **THEN** The guard passes.
