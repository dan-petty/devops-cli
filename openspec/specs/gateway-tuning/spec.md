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

### Requirement: Capability probes execution
The system SHALL run four standardized capability probes (5-field JSON, 10-tool choice, deep recall, and explicit prohibition) using production prompted formats during gateway tuning.

#### Scenario: Capability probes executed for deployment
- **WHEN** gateway tuning executes against active deployments without estimate mode
- **THEN** the system runs all four capability probes and captures response content and completion tokens

### Requirement: Capability scoring and repair tracking
The system SHALL score capability probe responses using deterministic evaluators in pydantic_evals and track whether response repair was required.

#### Scenario: Probes scored and repairs tracked
- **WHEN** capability probe responses are received
- **THEN** deterministic evaluators assess correctness across trials and response repair records repair occurrence

### Requirement: Persist and report measured capabilities
The system SHALL persist probe results per deployment in the run store and report measured capability scores in command outputs.

#### Scenario: Measured capabilities persisted and reported
- **WHEN** gateway tuning completes
- **THEN** run records persist capability probe results per deployment id and reports show measured pass rates or unmeasured status
