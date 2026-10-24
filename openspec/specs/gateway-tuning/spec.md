# gateway-tuning Specification

## Purpose
Measures and estimates AI gateway deployment concurrency capacity and token cost from spend records and hardware bandwidth.

## Requirements

### Requirement: Token cost from spend ledger
The system SHALL read token cost per review request for each backend from the spend ledger when records exist.

#### Scenario: Spend ledger contains tokens for backend
- **WHEN** gateway tuning runs and the spend ledger contains records for a backend
- **THEN** the tuner sets token cost from the ledger without sending synthetic probe requests

### Requirement: Fallback to probe for missing cost records
The system SHALL fall back to a synthetic probe request when the spend ledger contains no records for a backend.

#### Scenario: Spend ledger lacks records for backend
- **WHEN** gateway tuning runs and the spend ledger has no records for a backend
- **THEN** the tuner sends a synthetic probe request to measure token cost

### Requirement: No-load capacity estimation
The system SHALL calculate deployment capacity scaled by GPU memory bandwidth from a prior measured deployment when the estimate option is enabled.

#### Scenario: Estimate option scales capacity by GPU bandwidth
- **WHEN** the user executes gateway tuning with the estimate flag
- **THEN** the system calculates capacity using bandwidth ratio without sending network load to the backend

### Requirement: Persisted run records include estimate mode
The system SHALL record the estimate setting in gateway tuning run records.

#### Scenario: Run record contains estimate attribute
- **WHEN** a gateway tuning execution completes
- **THEN** the persisted run record includes the estimate field
