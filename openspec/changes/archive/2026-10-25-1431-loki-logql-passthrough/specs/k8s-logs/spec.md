# Spec Delta

## Purpose

Retrieves Kubernetes pod and cluster logs via direct LogQL queries to Loki or native kubectl log streaming.

## ADDED Requirements

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
