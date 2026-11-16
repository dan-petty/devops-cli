# Spec Delta

## MODIFIED Requirements

### Requirement: A verification pass follows the gates
When the caller gives a verifier, the planner SHALL run one verification for each plan after the plan passes `check_proposal` and `validate_change`, and before the job opens the draft pull request. The verifier SHALL be an agent of the task `ai.tasks.stage_review` with the read-only tools of the toolset `roadmap.stage.toolset`. Its request SHALL hold the issue, the plan and the capped start of each file that the plan cites. The pass SHALL NOT merge a pull request or mark one ready.

#### Scenario: A plan that passes the gates
- **WHEN** a plan passes the gates and the verifier finds nothing
- **THEN** the verifier runs once with a request that holds the issue, the plan and the cited files, and no message of the planner, and the job opens the draft pull request

#### Scenario: A long cited file
- **WHEN** a plan cites a file with more tokens than `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS`
- **THEN** the request holds only the first tokens of that file

#### Scenario: A plan that fails the gates
- **WHEN** the gates refuse a plan twice
- **THEN** the verifier gets no request

#### Scenario: No pull request is merged or marked ready
- **WHEN** the pass ends with findings
- **THEN** the draft pull request stays a draft and the job makes no merge call
