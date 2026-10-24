# Spec Delta

## ADDED Requirements

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
