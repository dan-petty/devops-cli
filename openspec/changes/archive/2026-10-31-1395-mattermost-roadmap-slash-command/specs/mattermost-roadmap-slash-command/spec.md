# Spec Delta

## Purpose

Enables Mattermost to invoke the `/roadmap` slash command against the in-cluster roadmap service webhook router to show repository and lane status.

## ADDED Requirements

### Requirement: Token authorization on slash command endpoint
The webhook router SHALL authenticate Mattermost slash command requests with an `Authorization: Token <token>` header matching the configured token using constant-time comparison. The router SHALL refuse unauthenticated or invalidly authenticated requests with HTTP 401.

#### Scenario: Valid token authorization
- **WHEN** a request arrives with a valid Authorization header matching the configured token
- **THEN** the router accepts the request and passes it to the provider handler

#### Scenario: Invalid or missing token
- **WHEN** a request arrives with a missing or mismatched token
- **THEN** the router rejects the request with HTTP 401 and logs a warning without the token value

### Requirement: Form urlencoded payload and responder execution
The webhook router SHALL parse `application/x-www-form-urlencoded` payloads for the Mattermost provider and reject JSON requests with HTTP 415. The router SHALL dispatch the command to a synchronous responder that returns an ephemeral response.

#### Scenario: URL-encoded payload handling
- **WHEN** a form payload arrives for the Mattermost provider
- **THEN** the router parses the form and returns an ephemeral reply

#### Scenario: JSON payload rejected
- **WHEN** a JSON payload arrives for the Mattermost provider
- **THEN** the router rejects the request with HTTP 415

### Requirement: Roadmap slash command parsing and status reply
The `/roadmap` slash command SHALL split arguments with `shlex.split`. `status` or empty arguments SHALL return the status of all configured repositories and lanes. `status <repo>` SHALL return the status of the specified repository. Unknown repositories or invalid subcommands SHALL return helpful error or usage messages.

#### Scenario: Status command without repository
- **WHEN** `/roadmap` or `/roadmap status` is received
- **THEN** the command returns running or idle status for all configured repositories and lanes

#### Scenario: Status command for specific repository
- **WHEN** `/roadmap status <repo>` is received
- **THEN** the command returns status for the specified repository's lanes

#### Scenario: Status command with unknown repository
- **WHEN** `/roadmap status <unknown>` is received
- **THEN** the command returns the list of known repositories

#### Scenario: Invalid subcommand
- **WHEN** an unrecognized subcommand is received
- **THEN** the command returns usage text

### Requirement: Chat command metrics
The service SHALL increment the Prometheus counter `devops_cli_service_chat_commands_total` with labels `command` and `result` for each processed slash command.

#### Scenario: Metric increment on command execution
- **WHEN** a `/roadmap` slash command is processed
- **THEN** the service increments `devops_cli_service_chat_commands_total` with command and result labels

### Requirement: Mattermost internal connection and network policies
The deployment manifests SHALL permit Mattermost to connect to `roadmap-service.devops.svc.cluster.local` via `MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS` and network policies permitting egress from Mattermost on TCP port 8000 and ingress to roadmap-service from Mattermost on TCP port 8000.

#### Scenario: Network policy configuration
- **WHEN** the manifests are applied
- **THEN** network policies allow traffic from Mattermost pods to roadmap-service pods on TCP port 8000
