## ADDED Requirements

### Requirement: The run record keeps the token cost per tier
The record of an implement run SHALL keep the token cost of each step under the tier that served it.

#### Scenario: Cost is recorded after a step completes
- **WHEN** a step completes on a given tier
- **THEN** the run record holds the token count of that step under that tier
