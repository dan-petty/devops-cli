## ADDED Requirements

### Requirement: Each roadmap job logs one result line for each attempt
The stage, implement, refine, refine judge, alternatives and intake jobs SHALL log one `roadmap job result` line for each attempt, with the job, repository, item, result, success, failure class, infrastructure flag, counts and version. A line SHALL hold numbers and fixed names only, never issue or model text.

#### Scenario: A stage round of three tried items
- **WHEN** a stage round stages one item, stops one on its budget, fails one after a gate return and leaves one out
- **THEN** three lines give `staged success=true`, `needs_split` and `failed class=plan_defect gate_returns=1`

#### Scenario: A killed implement Job
- **WHEN** the implement row reports a Job that the kernel killed for its memory after 1200 seconds
- **THEN** one line gives `result=stopped success=false class=oom infra=true seconds=1200`

#### Scenario: Issue text in a value
- **WHEN** a result or a name holds a space
- **THEN** the line holds `other` in its place
