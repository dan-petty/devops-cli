## ADDED Requirements

### Requirement: The replay reports a plan that leaves out the prompt reply key
The golden set SHALL hold a case whose plan adds a field to `StageProposal` and changes no reply key of the prompt, and the replay SHALL report that defect as caught by the `prompt_keys` gate.

#### Scenario: Recorded missing prompt key
- **WHEN** The replay runs the gates on a case with a `prompt_key_missing` defect whose gate is `prompt_keys`.
- **THEN** The replay reports the defect as caught, and a gate stops it when the gate no longer refuses the plan.

#### Scenario: A plan that names the reply key
- **WHEN** The replay runs the gates on a `good` case whose plan adds a field to `StageProposal` and changes the prompt with the reply key.
- **THEN** The `prompt_keys` gate finds no problem, and the replay reports no failure.
