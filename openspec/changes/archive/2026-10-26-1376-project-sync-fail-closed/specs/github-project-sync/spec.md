# Spec Delta

## Purpose

Enforce fail-closed behavior across GitHub Projects v2 board lookups, field provisioning, and repository linking.

## ADDED Requirements

### Requirement: Board lookup fail closed
The system SHALL raise a classified error or unread error when a board lookup command fails or returns malformed data.

#### Scenario: Lookup encounters server error
- **WHEN** GitHub returns an HTTP 500 error during project board lookup
- **THEN** system raises GitHubUnreadError and halts execution

#### Scenario: Lookup encounters malformed payload
- **WHEN** GitHub returns empty output or non-JSON data during board lookup
- **THEN** system raises GitHubUnreadError and halts execution

### Requirement: Field provisioning fail closed
The system SHALL read existing board fields through fail-closed field listing models and fail closed on field creation errors.

#### Scenario: Field listing fails
- **WHEN** field listing command exits non-zero or returns invalid payload
- **THEN** system raises an error and provisions no fields

#### Scenario: Field creation lacks scope
- **WHEN** field creation command fails with missing project scope
- **THEN** system raises GitHubScopeError naming the missing scope

### Requirement: Repository link fail closed
The system SHALL report repository linking errors and raise on non-zero command exits.

#### Scenario: Project link lacks scope
- **WHEN** linking a project board to a repository fails with a missing scope
- **THEN** system raises GitHubScopeError naming the missing scope

#### Scenario: Project link fails with non-zero exit
- **WHEN** linking a project board fails with an unclassified non-zero exit
- **THEN** system raises GitHubOperationError and reports the failure

### Requirement: Project listing fail closed
The system SHALL raise errors on failed project listings instead of returning empty results.

#### Scenario: Project listing command fails
- **WHEN** project listing command exits non-zero
- **THEN** system raises a classified or unread error instead of reporting zero boards

### Requirement: Restrict user owner cache
The system SHALL cache `@me` only when the owner argument matches the authenticated GitHub user.

#### Scenario: Organization lookup failure does not cache user
- **WHEN** an organization project lookup fails and fallback succeeds
- **THEN** system does not associate the organization name with `@me` in owner cache
