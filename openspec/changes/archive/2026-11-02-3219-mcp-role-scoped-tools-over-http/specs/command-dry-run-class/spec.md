## MODIFIED Requirements

### Requirement: server-request-plans
The commands `mcp serve` and `serve` SHALL carry the `request-plan` dry-run class and expose `--dry-run`. Under `--dry-run` each command SHALL start no server and open no socket. It SHALL print the bind and start requests of the real call. `mcp serve` SHALL refuse a host that is not loopback without `--allow-remote`, and over `streamable-http` a missing or short `mcp.token`, as the real run does. `serve --service --dry-run` SHALL load no settings and read no credential.

#### Scenario: Dry run on mcp serve over sse
- **WHEN** a user runs `devops mcp serve --transport sse --host 127.0.0.1 --port 9090 --dry-run` with `run_mcp_server` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9090` and a start request for the `sse` transport

#### Scenario: Dry run on mcp serve over streamable-http
- **WHEN** a user runs `devops mcp serve --transport streamable-http --port 9090 --dry-run` with a token of 32 characters or more
- **THEN** the plan prints a bind request for `127.0.0.1:9090` and a start request for the `streamable-http` transport, and prints no token

#### Scenario: Dry run on mcp serve over streamable-http without a token
- **WHEN** a user runs `devops mcp serve --transport streamable-http --dry-run` with no `mcp.token`
- **THEN** the command refuses as the real run does and prints no plan

#### Scenario: Dry run on mcp serve with a remote host
- **WHEN** a user runs `devops mcp serve --transport sse --host 192.0.2.10 --dry-run`
- **THEN** the command refuses the host as the real run does and prints no plan

#### Scenario: Dry run on serve
- **WHEN** a user runs `devops --dry-run serve --host 127.0.0.1 --port 9000 --workers 2` with `uvicorn.run` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9000` and a start request that names 2 workers
