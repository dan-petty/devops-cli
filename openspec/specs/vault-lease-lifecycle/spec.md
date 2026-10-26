# vault-lease-lifecycle Specification

## Purpose
Enables revocation of HashiCorp Vault dynamic secret leases and manages session-scoped lease registry state.

## Requirements

### Requirement: Vault lease revocation requires explicit lease identifier
The system SHALL require an explicit `--revoke` option when running `devops vault leases`, rejecting invocations without a lease identifier.

#### Scenario: Missing revoke option rejects execution
- **WHEN** user executes `devops vault leases` without the `--revoke` option
- **THEN** the command exits with code 2 and reports missing option `--revoke`

#### Scenario: Revoke single lease
- **WHEN** user executes `devops vault leases --revoke <lease-id>` with a valid token
- **THEN** the system issues a POST request to Vault `sys/leases/revoke` and reports successful revocation

### Requirement: Session lease registry rebuilds on credential changes
The system SHALL manage a session-scoped lease registry that rebuilds automatically when Vault coordinates or authentication tokens change.

#### Scenario: Same credentials reuse registry
- **WHEN** session lease registry is retrieved with unchanged address and token
- **THEN** the system returns the existing registry instance

#### Scenario: Changed credentials rebuild registry
- **WHEN** session lease registry is retrieved with a different address or token
- **THEN** the system instantiates and returns a new registry instance for the new credentials
