# Spec Delta

## ADDED Requirements

### Requirement: The MCP tool k8s_logs publishes no Loki URL
The MCP tool `k8s_logs` SHALL publish no `loki_url` parameter. It SHALL publish `pod`, `query_arg`, `query`, `container`, `namespace`, `follow`, `tail`, `limit`, `since` and `dry_run`. Its LogQL query SHALL go to the default Loki. The default Loki is the Loki that `devops k8s logs` queries when it gets no `--loki-url`. The request path SHALL be `/loki/api/v1/query_range`. A call that gives `loki_url` SHALL fail and send no request, and `devops k8s logs` SHALL keep `--loki-url`.

#### Scenario: The tool schema
- **WHEN** an MCP client lists the tools
- **THEN** `k8s_logs` publishes `pod`, `query_arg`, `query`, `container`, `namespace`, `follow`, `tail`, `limit`, `since` and `dry_run`, and no `loki_url`

#### Scenario: A call that gives a Loki URL
- **WHEN** a client calls `k8s_logs` with `loki_url` set to a loopback URL, or to a URL whose host answers a private address
- **THEN** the call fails and the socket gets no dial to that host
- **AND** the error holds no text from an answer of that host

#### Scenario: The default Loki
- **WHEN** a client calls `k8s_logs` with a LogQL query and no `loki_url`
- **THEN** the tool sends `GET /loki/api/v1/query_range` with the query to `localhost` on port 3100
- **AND** the tool returns the log lines of the answer

#### Scenario: The command keeps its URL option
- **WHEN** a person runs `devops k8s logs '{app="web"}' --loki-url http://example.com:3100`
- **THEN** the request goes to `example.com` on port 3100
