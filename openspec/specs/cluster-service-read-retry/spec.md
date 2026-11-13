# cluster-service-read-retry Specification

## Purpose
The retry policy of the reads of a cluster service (Prometheus, Loki, Grafana and the addresses of `get_json`): which requests and failures it sends again, its waits and its time bound, the calls that keep one attempt, and the one error line that ends a read that fails.

## Requirements

### Requirement: A read of a cluster service is sent again after a transient failure
A client built with `http_client(level, retries=SERVICE_READ_RETRY)` SHALL send a GET, HEAD or OPTIONS request again when the reply has the status 429, 502, 503 or 504, or when the request fails with `ConnectError`, `ConnectTimeout`, `ReadError`, `ReadTimeout` or `RemoteProtocolError`. It SHALL make at most 4 attempts. When the attempts end, the client SHALL give the last reply, or raise the last network error, as one attempt does.

#### Scenario: Prometheus answers after two 503 replies
- **WHEN** Prometheus answers 503 twice and then 200 with a vector
- **THEN** `PrometheusClient.query` returns the vector
- **AND** the fake has received 3 requests

#### Scenario: Every connect is refused
- **WHEN** each connect to Prometheus is refused
- **THEN** the client has sent 4 attempts
- **AND** it waited 3 times

### Requirement: A read that did not fail for a transient cause is sent once
The client SHALL send a request one time when the reply has a 4xx status other than 429, or a 500 status. It SHALL send a request with a method other than GET, HEAD or OPTIONS one time, whatever its reply. It SHALL send no request again that the egress check refused.

#### Scenario: A 400 reply
- **WHEN** Prometheus answers a query with 400
- **THEN** the fake has received 1 request

#### Scenario: A POST that gets 503
- **WHEN** Grafana answers the import of a dashboard with 503
- **THEN** the fake has received 1 request

#### Scenario: An address that the egress level refuses
- **WHEN** a client at the loopback level sends a GET to a private address
- **THEN** the client raises `SSRFBlockedError`
- **AND** the fake has received no request

### Requirement: The attempts back off with jitter within a time bound
Each wait SHALL back off exponentially from 1 s with a jitter of up to 1 s, and SHALL be at least the delay of the `Retry-After` header of the reply. The client SHALL start no attempt when the time since the first attempt plus the next wait is 20 s or more. 20 s SHALL be less than `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS`.

#### Scenario: The waits of three 503 replies
- **WHEN** Prometheus answers 503 to each attempt
- **THEN** the client waits three times, between 1 s and 2 s, between 2 s and 3 s, and between 4 s and 5 s

#### Scenario: A Retry-After header
- **WHEN** Prometheus answers 429 with `Retry-After: 6` and then 200
- **THEN** the client waits 6 s before the second attempt

#### Scenario: A Retry-After past the time bound
- **WHEN** Prometheus answers 503 with `Retry-After: 30`
- **THEN** the client sends 1 request and gives the 503 reply

#### Scenario: Slow attempts use the time bound
- **WHEN** each attempt fails with `ConnectTimeout` after 10 s
- **THEN** the client sends 2 attempts

### Requirement: The last failure of a read is one error line
A failed request of `PrometheusClient`, of `query_loki_metrics`, of `GrafanaClient` or of `get_json` SHALL raise `ServiceRequestError`, a `DevOpsCLIError` with exit status 1. Its message SHALL be one line that names the service, the HTTP status and its reason or the network error, the number of attempts, the time in seconds and a hint. For a 4xx reply whose JSON body has an `error` field, the line SHALL hold the `errorType` and the `error` of the body.

#### Scenario: devops prometheus query while Prometheus stays down
- **WHEN** Prometheus answers 503 to each attempt of `devops prometheus query up`
- **THEN** the command exits 1
- **AND** it prints one line that holds `Prometheus`, `503`, `4 attempts` and `try again`
- **AND** it prints no traceback

#### Scenario: Prometheus refuses a query
- **WHEN** Prometheus answers `devops prometheus query` with 400 and the body `{"status": "error", "errorType": "bad_data", "error": "1:9: parse error: unexpected <by>"}`
- **THEN** the command exits 1
- **AND** it prints one line that holds `400`, `bad_data`, `parse error: unexpected <by>` and `1 attempt`

#### Scenario: Loki stays down during the grades
- **WHEN** Loki answers 503 to each attempt of a metric query
- **THEN** `query_loki_metrics` raises `ServiceRequestError` whose message holds `Loki`, `503` and `4 attempts`

### Requirement: Each client of a cluster service uses the policy
The Loki metric queries (`query_loki_metrics`), the reads of `GrafanaClient` and `get_json` SHALL use `SERVICE_READ_RETRY`. `get_json` SHALL take a `retries` argument whose default is `SERVICE_READ_RETRY`.

#### Scenario: Loki answers after a 503
- **WHEN** Loki answers the first metric query with 503 and then with a vector
- **THEN** `query_loki_metrics` returns the vector

#### Scenario: Grafana answers after a 503
- **WHEN** Grafana answers the search of dashboards with 503 and then with a list
- **THEN** `GrafanaClient.list_dashboards` returns the list

#### Scenario: A Service address answers after a 503
- **WHEN** a plain URL answers `get_json` with 503 and then with a JSON object
- **THEN** `get_json` returns the object

### Requirement: A probe that reports down fast sends one attempt
`reaches_service`, the poll of the health route in `forward_service` and the telemetry panel of the dashboard SHALL send each request one time. A client with a retry option and a client without one SHALL NOT share a pooled client.

#### Scenario: The API server cannot dial the Service
- **WHEN** the API server answers the GET of `reaches_service` with 503 and a `Status` of reason `ServiceUnavailable`
- **THEN** `reaches_service` returns false
- **AND** the fake has received 1 request

#### Scenario: The forward poll gets a 503
- **WHEN** the health route answers the poll of the forward with 503
- **THEN** the poll reports no answer after 1 request
