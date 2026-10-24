# Spec Delta

## Purpose

Enables reclamation of stopped containers, unused networks, dangling images, and unused volumes through the Docker engine client.

## ADDED Requirements

### Requirement: Resource prune execution order
The system SHALL prune stopped containers, unused networks, and dangling images sequentially in that exact order when pruning without volume deletion.

#### Scenario: Standard prune without volumes
- **WHEN** user executes `devops docker prune --force`
- **THEN** the system calls `containers.prune()`, `networks.prune()`, and `images.prune()` in order without filters, and skips `volumes.prune()`

### Requirement: Volume prune execution
The system SHALL prune unused volumes after containers, networks, and images when the user specifies the volumes option.

#### Scenario: Prune with volumes option
- **WHEN** user executes `devops docker prune --force --volumes`
- **THEN** the system calls `containers.prune()`, `networks.prune()`, `images.prune()`, and `volumes.prune()` in sequential order

### Requirement: Reclaimed space calculation
The system SHALL aggregate space reclaimed values across collection prune responses and report total megabytes reclaimed.

#### Scenario: Space aggregation with missing or null values
- **WHEN** prune responses return reclaimed values or omit the reclaimed space field
- **THEN** missing or null values count as zero and the sum displays in the success message

### Requirement: Error reporting without traceback
The system SHALL surface engine API errors with exit code 1 and a single error line without a Python traceback.

#### Scenario: Daemon error occurs during prune
- **WHEN** the engine API raises an error during container, network, image, or volume prune
- **THEN** the system displays the daemon error text, emits no traceback, and exits with code 1
