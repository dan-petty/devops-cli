# Spec Delta

## Purpose
Defines which Vault `devops vault status` and its MCP tool ask for health, and which address a caller can give. A model never chooses the address, and no address can change the path of the request.

## ADDED Requirements

### Requirement: The MCP tool vault_status publishes no address
The MCP tool `vault_status` SHALL publish no `vault_addr` parameter. It SHALL publish `dry_run` and no other parameter. Its request SHALL go to the Vault that `VAULT_ADDR` or `DEVOPS_CLI_VAULT_ADDR` names, and its path SHALL be `/v1/sys/health`. A call that gives `vault_addr` SHALL fail and send no request. A call with neither variable set SHALL fail, send no request, and name both variables in its error.

#### Scenario: The tool schema
- **WHEN** an MCP client lists the tools
- **THEN** `vault_status` publishes the parameter `dry_run` and no other

#### Scenario: A call that gives an address
- **WHEN** a client calls `vault_status` with `vault_addr` set to `http://127.0.0.1:8200/some/path?x=`
- **THEN** the call fails and the socket gets no dial to that host
- **AND** the reply holds no value from an answer of that host

#### Scenario: The configured Vault
- **WHEN** a client calls `vault_status` with no argument and `VAULT_ADDR` is `http://example.com:8200`
- **THEN** the tool sends `GET /v1/sys/health` to `example.com` on port 8200
- **AND** the tool returns the version and cluster name of the answer

#### Scenario: No configured Vault
- **WHEN** a client calls `vault_status` with no argument and neither `VAULT_ADDR` nor `DEVOPS_CLI_VAULT_ADDR` is set
- **THEN** the call fails, the socket gets no dial, and the error names `VAULT_ADDR` and `DEVOPS_CLI_VAULT_ADDR`

### Requirement: The Vault address names the whole service
The Vault broker SHALL refuse an address that holds a query or a fragment, which means the character `?` or `#`, before it sends any request. The error SHALL NOT repeat the address.

#### Scenario: An address with a query or a fragment
- **WHEN** the address is `http://example.com:8200/some/path?x=` or `http://example.com:8200/some/path#`
- **THEN** the broker raises a configuration error that says the address cannot have a query or fragment

### Requirement: The command keeps its address option
`devops vault status` SHALL keep the option `--addr` for a person at the command line.

#### Scenario: A person gives an address
- **WHEN** a person runs `devops vault status --addr http://example.com:8201`
- **THEN** the request goes to `example.com` on port 8201
