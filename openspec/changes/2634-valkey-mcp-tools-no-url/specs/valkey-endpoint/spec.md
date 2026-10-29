# Spec Delta

## ADDED Requirements

### Requirement: The MCP Valkey tools publish no URL
The MCP tools `valkey_ping`, `valkey_stats`, `valkey_info`, `valkey_get`, `valkey_set` and `valkey_flush` SHALL publish no `url` parameter. Each tool SHALL dial the endpoint of `valkey.url` and SHALL send the Valkey password only to it. A call that gives `url` SHALL fail and open no connection. The nine `devops valkey` commands SHALL keep `--url`. A person types it, so the password goes to the host that it names.

#### Scenario: The tool schemas
- **WHEN** an MCP client lists the six tools
- **THEN** `valkey_ping` and `valkey_stats` publish no parameter, `valkey_info` publishes `section`, `valkey_get` publishes `key`, `valkey_set` publishes `key`, `value`, `ex` and `dry_run`, and `valkey_flush` publishes `all_databases` and `dry_run`

#### Scenario: A call that gives a URL
- **WHEN** a client calls one of the six tools with `url` set to a loopback URL, and `valkey.password` is set
- **THEN** the call fails, the server at that URL gets no connection, and so the password is not on the wire

#### Scenario: The configured server
- **WHEN** a client calls one of the six tools, `valkey.url` names a loopback server, and `valkey.password` is set
- **THEN** the server receives `AUTH` with the password, and then the command of the tool

#### Scenario: A person types the URL
- **WHEN** a person runs `devops valkey ping --url valkey://127.0.0.1:<port>/3`, and `valkey.password` is set
- **THEN** the server at that URL receives `AUTH` with the password, `SELECT 3` and then `PING`, and the command exits 0
