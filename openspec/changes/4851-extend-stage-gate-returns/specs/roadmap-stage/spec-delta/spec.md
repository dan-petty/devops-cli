## MODIFIED Requirements

### Requirement: The change passes the OpenSpec validation
When the `openspec` binary is on `PATH`, the job SHALL run `openspec validate <change> --strict --json` on the change before it writes to git. A failed validation SHALL go back to the model with the output of the tool, `roadmap.stage.gate_returns` times at most, and one more time when the item gets its extra return (`roadmap-stage/returns`, #4851). A failure after the last return SHALL stop the item. Without the binary, the comment on the issue SHALL say that the validation did not run.

#### Scenario: The validation fails once
- **WHEN** the first plan fails the validation and the second plan passes it
- **THEN** the job stages the second plan and the model got the output of the first failure

#### Scenario: The validation fails twice
- **WHEN** the first plan and the plan after each return fail the validation
- **THEN** the job stops the item after the last return, pushes nothing, and reports the output of the last failure

#### Scenario: Each failed validation is new
- **WHEN** each plan fails the validation with an output that differs from the output before it
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` + 1 requests, and the failure says that the item used its extra return

#### Scenario: No openspec binary
- **WHEN** the `openspec` binary is not on `PATH`
- **THEN** the job stages the item and its comment says that the validation did not run
