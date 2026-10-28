## MODIFIED Requirements

### Requirement: The wait is not gate time
The time a run waits for a slot SHALL NOT count in the elapsed time of the gate, in its summary or in its over-budget warning. The run SHALL record the wait as one observation of the histogram `devops_cli_ci_gate_slot_wait_seconds`.

#### Scenario: A long wait and a fast gate
- **WHEN** a run waits 600 s for a slot and then runs checks that take 30 s
- **THEN** the summary reports an elapsed time of about 30 s and no over-budget warning
- **AND** the histogram `devops_cli_ci_gate_slot_wait_seconds` has one observation of about 600
