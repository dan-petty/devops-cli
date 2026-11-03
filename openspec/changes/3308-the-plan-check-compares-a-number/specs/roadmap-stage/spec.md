## ADDED Requirements

### Requirement: A plan number beside a constant matches the staged value
The plan check SHALL refuse a plan when a decimal number in the same sentence as a known module-level integer constant of the staged tree differs from the value of that constant.

#### Scenario: Summary bound mismatch
- **WHEN** A spec scenario says `SUMMARY_MAX_CHARS` is 40, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns one problem that names `SUMMARY_MAX_CHARS`, 40 and 60.

#### Scenario: Summary bound match
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 60, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A bound after the constant name
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` holds 60 characters, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

### Requirement: A constant that the staged tree does not define is ignored
The plan check MUST skip a constant name that the staged tree does not define as a module-level integer assignment.

#### Scenario: New plan constant
- **WHEN** A design decision names `PLAN_SUMMARY_MAX_CHARS = 47`, and the staged tree does not define `PLAN_SUMMARY_MAX_CHARS`.
- **THEN** The check returns no problem about `PLAN_SUMMARY_MAX_CHARS`.

#### Scenario: Non-literal assignment
- **WHEN** A staged module sets `SUMMARY_MAX_CHARS` from a call, and the plan says `SUMMARY_MAX_CHARS` is 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

### Requirement: The check reads constants without running staged code
The plan check MUST read the constant values with the Python `ast` module and MUST NOT import or execute a staged file.

#### Scenario: A staged module with a side effect
- **WHEN** A staged Python module writes a file at import, and the plan says `SUMMARY_MAX_CHARS` is 60.
- **THEN** The check writes no file and returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: An alias to another constant
- **WHEN** A staged module sets `BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` and another staged module sets `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS = 800`, and the plan says `BODY_MAX_CHARS` is 800.
- **THEN** The check returns no problem about `BODY_MAX_CHARS`.

### Requirement: The task commands carry no constant claim
The plan check MUST NOT compare a number in `tasks.md` with a constant.

#### Scenario: Task command number
- **WHEN** `tasks.md` holds `SUMMARY_MAX_CHARS` and 40 in one command, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

### Requirement: The prompt asks for the staged value of a constant
The plan stage prompt SHALL tell the model to cite the staged value of each constant that the plan relies on.

#### Scenario: Prompt rule
- **WHEN** The prompt rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The text holds an instruction to cite the staged value of each constant that the plan relies on.
