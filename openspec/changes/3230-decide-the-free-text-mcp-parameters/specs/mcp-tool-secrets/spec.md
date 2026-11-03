## ADDED Requirements

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
