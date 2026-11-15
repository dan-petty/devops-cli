## ADDED Requirements

### Requirement: The stop records the action left in the record
The implement job SHALL record the action left in `implement.left_action` when a step stops.

#### Scenario: A stop with the action left amend
- **WHEN** A step stops with the class `plan_defect` and no action taken, whose action left is `amend`.
- **THEN** The job record of the issue holds `implement.left_action` with the value `amend`.

### Requirement: A retry and a clear rule remove the action left with the stop
A retry comment and each clear rule of the Service SHALL remove `implement.left_action` with `implement.stopped`.

#### Scenario: A retry comment on a stopped item
- **WHEN** A trusted person comments `implement: retry` on an item whose record holds `implement.stopped`, `implement.failure` and `implement.left_action`.
- **THEN** The job record holds none of `implement.stopped`, `implement.failure` and `implement.left_action`.

#### Scenario: A clear by digest on a stopped item
- **WHEN** The Service clears a stop of the class `ci_infra` by digest on an item whose record holds `implement.left_action`.
- **THEN** The job record holds neither `implement.stopped` nor `implement.left_action`.
