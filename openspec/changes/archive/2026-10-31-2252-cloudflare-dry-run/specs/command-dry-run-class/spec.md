# Spec Delta

## ADDED Requirements

### Requirement: cloudflare-request-plans
Ten commands in `cloudflare` SHALL carry the `request-plan` dry-run class:
`cloudflare status`, `cloudflare service-status`, `cloudflare dns list`, `cloudflare dns sync`, `cloudflare dns delete`, `cloudflare tunnel routes`, `cloudflare tunnel sync`, `cloudflare access status`, `cloudflare access sync`, and `cloudflare access policies`.
Under dry run, each command SHALL make zero external HTTP requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on cloudflare status
- **WHEN** user executes `devops cloudflare status --dry-run`
- **THEN** the command prints planned token verification and zone details requests and makes zero external calls

#### Scenario: Dry run on cloudflare service-status
- **WHEN** user executes `devops cloudflare service-status --dry-run`
- **THEN** the command prints planned statuspage summary requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns list
- **WHEN** user executes `devops cloudflare dns list --dry-run`
- **THEN** the command prints planned DNS record listing requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns sync
- **WHEN** user executes `devops cloudflare dns sync --dry-run`
- **THEN** the command prints planned DNS record reconciliation requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns delete
- **WHEN** user executes `devops cloudflare dns delete example.com --dry-run`
- **THEN** the command prints planned DNS record deletion requests and makes zero external calls

#### Scenario: Dry run on cloudflare tunnel routes
- **WHEN** user executes `devops cloudflare tunnel routes --dry-run`
- **THEN** the command prints planned tunnel configuration retrieval requests and makes zero external calls

#### Scenario: Dry run on cloudflare tunnel sync
- **WHEN** user executes `devops cloudflare tunnel sync --dry-run`
- **THEN** the command prints planned tunnel configuration update requests and makes zero external calls

#### Scenario: Dry run on cloudflare access status
- **WHEN** user executes `devops cloudflare access status --dry-run`
- **THEN** the command prints planned Access application listing requests and makes zero external calls

#### Scenario: Dry run on cloudflare access sync
- **WHEN** user executes `devops cloudflare access sync --domain example.com --allowed-emails user@example.com --dry-run`
- **THEN** the command prints planned Access application and policy configuration requests and makes zero external calls

#### Scenario: Dry run on cloudflare access policies
- **WHEN** user executes `devops cloudflare access policies app-123 --dry-run`
- **THEN** the command prints planned Access policy retrieval requests and makes zero external calls
