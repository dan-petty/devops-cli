# Spec Delta

## ADDED Requirements

### Requirement: valkey-request-plans
Nine commands in `valkey` SHALL carry the `request-plan` dry-run class:
`valkey backup`, `valkey cli`, `valkey flush`, `valkey get`, `valkey info`, `valkey keys`, `valkey ping`, `valkey set`, and `valkey stats`.
Under dry run, each command SHALL make zero external network requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on valkey ping
- **WHEN** user executes `devops valkey ping --dry-run`
- **THEN** the command prints planned PING request and makes zero external calls

#### Scenario: Dry run on valkey info
- **WHEN** user executes `devops valkey info --dry-run`
- **THEN** the command prints planned INFO request and makes zero external calls

#### Scenario: Dry run on valkey stats
- **WHEN** user executes `devops valkey stats --dry-run`
- **THEN** the command prints planned INFO and DBSIZE requests and makes zero external calls

#### Scenario: Dry run on valkey keys
- **WHEN** user executes `devops valkey keys --dry-run`
- **THEN** the command prints planned KEYS request and makes zero external calls

#### Scenario: Dry run on valkey get
- **WHEN** user executes `devops valkey get mykey --dry-run`
- **THEN** the command prints planned GET request and makes zero external calls

#### Scenario: Dry run on valkey set
- **WHEN** user executes `devops valkey set mykey myval --dry-run`
- **THEN** the command prints planned SET request with placeholder and makes zero external calls

#### Scenario: Dry run on valkey flush
- **WHEN** user executes `devops valkey flush --dry-run`
- **THEN** the command prints planned FLUSHDB request and makes zero external calls

#### Scenario: Dry run on valkey backup
- **WHEN** user executes `devops valkey backup --dry-run`
- **THEN** the command prints planned BGSAVE request and makes zero external calls

#### Scenario: Dry run on valkey cli
- **WHEN** user executes `devops valkey cli ping --dry-run`
- **THEN** the command prints planned CLI execution request and makes zero external calls

### Requirement: vault-request-plans
Seven commands in `vault` SHALL carry the `request-plan` dry-run class:
`vault get`, `vault leases`, `vault login`, `vault logout`, `vault set`, `vault status`, and `vault sync`.
Under dry run, each command SHALL make zero external HTTP requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on vault status
- **WHEN** user executes `devops vault status --dry-run`
- **THEN** the command prints planned sys/health request and makes zero external calls

#### Scenario: Dry run on vault get
- **WHEN** user executes `devops vault get secret/data/app --dry-run`
- **THEN** the command prints planned secret retrieval request and makes zero external calls

#### Scenario: Dry run on vault set
- **WHEN** user executes `devops vault set secret/data/app KEY=VAL --dry-run`
- **THEN** the command prints planned secret storage request with placeholders and makes zero external calls

#### Scenario: Dry run on vault sync
- **WHEN** user executes `devops vault sync secret/data/app --dry-run`
- **THEN** the command prints planned secret synchronization request and makes zero external calls

#### Scenario: Dry run on vault login
- **WHEN** user executes `devops vault login --method approle --role-id r --secret-id s --dry-run`
- **THEN** the command prints planned authentication request with placeholders and makes zero external calls

#### Scenario: Dry run on vault logout
- **WHEN** user executes `devops vault logout --dry-run`
- **THEN** the command prints planned token revocation request and makes zero external calls

#### Scenario: Dry run on vault leases
- **WHEN** user executes `devops vault leases --revoke lease-1 --dry-run`
- **THEN** the command prints planned lease revocation request and makes zero external calls

### Requirement: vault-no-external-request
The `vault audit` command SHALL carry the `no-external-request` dry-run class. Under dry run, the command executes normally and inspects in-process audit records.

#### Scenario: Dry run on vault audit
- **WHEN** user executes `devops --dry-run vault audit`
- **THEN** the command executes without error and prints session credential access audit records
