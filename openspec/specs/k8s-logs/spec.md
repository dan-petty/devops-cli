# k8s-logs Specification

## Purpose
Retrieves Kubernetes pod and cluster logs via direct LogQL queries to Loki or native kubectl log streaming.

## Requirements

### Requirement: Direct LogQL passthrough to Loki
`devops k8s logs` SHALL send the user LogQL query to the Loki query endpoint byte for byte without rewriting or dropping matchers. It SHALL pass `since`, `limit`, and `direction` directly as HTTP query parameters.

#### Scenario: LogQL query with regex matcher sent to Loki
- **WHEN** the user executes `devops k8s logs '{app=~"api.*"} |= "error"'` against Loki
- **THEN** the exact query string `{app=~"api.*"} |= "error"` is sent to `/loki/api/v1/query_range`

#### Scenario: Duration parameter passed to Loki unchanged
- **WHEN** the user executes `devops k8s logs '{app="web"}' --since 1h30m`
- **THEN** the request parameter `since` sent to Loki is `1h30m`

### Requirement: Namespace selector validation
When `--namespace` is specified, `devops k8s logs` SHALL require the query stream selector to contain a matching namespace. If the query selector lacks a namespace, the command SHALL fail before sending any request and print the suggested selector.

#### Scenario: Missing namespace in query selector
- **WHEN** the user runs `devops k8s logs '{app="api"}' --namespace prod`
- **THEN** the command fails before any network request and prints that the query selector lacks namespace 'prod' and suggests `{app="api", namespace="prod"}`

#### Scenario: Matching namespace in query selector
- **WHEN** the user runs `devops k8s logs '{app="api", namespace="prod"}' --namespace prod`
- **THEN** the query is sent to Loki byte for byte

#### Scenario: Conflicting namespace in query selector
- **WHEN** the user runs `devops k8s logs '{app="api", namespace="dev"}' --namespace prod`
- **THEN** the command raises a conflicting namespace error before any network request

### Requirement: Egress policy enforcement for Loki
Loki HTTP requests SHALL be issued through the project HTTP client factory configured at the private egress level.

#### Scenario: Loki connection uses private egress level
- **WHEN** `devops k8s logs` executes a query against a Loki URL
- **THEN** the HTTP request is dispatched through the egress factory client at `EgressLevel.PRIVATE`

### Requirement: Kubectl fallback validation and execution
When Loki is unavailable, the fallback logging engine SHALL support only queries with equality label matchers and substring filters (`|=`). It SHALL run `kubectl logs` with `-l <selector>`. Queries containing non-equality matchers, pipeline format stages, or label filters SHALL be refused with an error referencing `loki.url`.

#### Scenario: Fallback runs kubectl logs with label selector
- **WHEN** Loki is unreachable and the user executes `{app="api"} |= "error"`
- **THEN** the fallback invokes `kubectl logs` with `-l app=api` and filters lines containing `error`

#### Scenario: Fallback refuses regex matcher
- **WHEN** Loki is unreachable and the query contains `{app=~"api.*"}`
- **THEN** the fallback raises an error mentioning `loki.url`

#### Scenario: Fallback refuses not-equal matcher
- **WHEN** Loki is unreachable and the query contains `{app!="api"}` or `!= "error"`
- **THEN** the fallback raises an error mentioning `loki.url`

#### Scenario: Fallback refuses label filter
- **WHEN** Loki is unreachable and the query contains `| level="error"`
- **THEN** the fallback raises an error mentioning `loki.url`

#### Scenario: Fallback refuses json pipeline
- **WHEN** Loki is unreachable and the query contains `| json`
- **THEN** the fallback raises an error mentioning `loki.url`

### Requirement: The Loki client looks up its host one time for each query
A Loki query SHALL resolve the host of the Loki URL one time, at the connect, and SHALL make no lookup before it. A Loki URL whose scheme is not `http` or `https` SHALL fail with no lookup.

#### Scenario: One Loki query
- **WHEN** a LogQL query runs against `http://example.com:3100`
- **THEN** `example.com` is looked up one time, and the socket gets the address of that lookup

#### Scenario: A Loki URL that is not HTTP
- **WHEN** a LogQL query runs against `ftp://example.com:3100`
- **THEN** the query fails with `httpx2.UnsupportedProtocol` and `example.com` is not looked up

### Requirement: The MCP tool k8s_logs publishes no Loki URL
The MCP tool `k8s_logs` SHALL publish `pod`, `query_arg`, `query`, `container`, `namespace`, `follow`, `tail`, `limit`, `since` and `dry_run`, and no `loki_url` parameter. Its LogQL query SHALL go to the default Loki: the Loki that `devops k8s logs` queries with no `--loki-url`, which is `loki.url`, else `http://localhost:3100`. The request path SHALL be `/loki/api/v1/query_range`. A call that gives `loki_url` SHALL fail and send no request, and `devops k8s logs` SHALL keep `--loki-url`.

#### Scenario: The tool schema
- **WHEN** an MCP client lists the tools
- **THEN** `k8s_logs` publishes `pod`, `query_arg`, `query`, `container`, `namespace`, `follow`, `tail`, `limit`, `since` and `dry_run`, and no `loki_url`

#### Scenario: A call that gives a Loki URL
- **WHEN** a client calls `k8s_logs` with `loki_url` set to a loopback URL, or to a URL whose host answers a private address
- **THEN** the call fails and the socket gets no dial to that host
- **AND** the error holds no text from an answer of that host

#### Scenario: The default Loki
- **WHEN** a client calls `k8s_logs` with a LogQL query and no `loki_url`, and `loki.url` is not set
- **THEN** the tool sends `GET /loki/api/v1/query_range` with the query to `localhost` on port 3100
- **AND** the tool returns the log lines of the answer

#### Scenario: A configured Loki
- **WHEN** a client calls `k8s_logs` with a LogQL query and no `loki_url`, and `loki.url` is `http://example.com:3100`
- **THEN** the tool sends `GET /loki/api/v1/query_range` with the query to `example.com` on port 3100

#### Scenario: A configured Loki and a call that gives a Loki URL
- **WHEN** `loki.url` is `http://example.com:3100` and a client calls `k8s_logs` with `loki_url` set to `http://127.0.0.1:3100`
- **THEN** the call fails and the socket gets no dial

#### Scenario: The command keeps its URL option
- **WHEN** a person runs `devops k8s logs '{app="web"}' --loki-url http://example.com:3100`
- **THEN** the request goes to `example.com` on port 3100

### Requirement: The Loki address of a log query
A log query SHALL go to the first of these that is set: the option `--loki-url`, the setting `loki.url`, and `http://localhost:3100`. `devops k8s logs`, its `--dry-run` plan, the live log pane and the MCP tool `k8s_logs` SHALL use this address. The client SHALL dial it at the private egress level, whatever `ai.allow_private_network` says.

#### Scenario: The setting names the Loki
- **WHEN** `loki.url` is `http://example.com:3100` and `devops k8s logs '{app="web"}'` runs with no `--loki-url`
- **THEN** the request is `GET /loki/api/v1/query_range` to `example.com` on port 3100

#### Scenario: The option wins over the setting
- **WHEN** `loki.url` is `http://example.com:3100` and `devops k8s logs '{app="web"}' --loki-url http://192.0.2.1:3100` runs
- **THEN** the socket gets one dial, to `192.0.2.1` on port 3100, and `example.com` is not looked up

#### Scenario: No option and no setting
- **WHEN** `loki.url` is not set and `devops k8s logs '{app="web"}'` runs with no `--loki-url`
- **THEN** the request goes to `localhost` on port 3100

#### Scenario: The dry-run plan shows the setting
- **WHEN** `loki.url` is `http://example.com:3100` and `devops k8s logs '{app="web"}' --dry-run` runs
- **THEN** the plan holds one `GET` request whose target starts with `http://example.com:3100/loki/api/v1/query_range`, and the command sends no request

#### Scenario: The setting names a loopback or private host
- **WHEN** `loki.url` is `http://example.com:3100`, `ai.allow_private_network` is false, and `example.com` answers `127.0.0.1` or `192.0.2.10`
- **THEN** the socket dials that address

#### Scenario: The setting names a cloud metadata host
- **WHEN** `loki.url` is `http://example.com:3100` and `example.com` answers `169.254.169.254`
- **THEN** the query raises `SSRFBlockedError` and the socket gets no dial
