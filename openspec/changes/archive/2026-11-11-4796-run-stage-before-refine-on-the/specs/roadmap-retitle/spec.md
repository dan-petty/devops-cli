## MODIFIED Requirements

### Requirement: A Service row runs the job
The model lane SHALL hold a row named `retitle` just before `stage`, and `DEFAULT_DUE_TABLE` SHALL include it.

#### Scenario: Row order
- **WHEN** `MODEL_LANE_ROWS` is read.
- **THEN** it holds `retitle` just before `stage`, and `DEFAULT_DUE_TABLE` holds it too.
