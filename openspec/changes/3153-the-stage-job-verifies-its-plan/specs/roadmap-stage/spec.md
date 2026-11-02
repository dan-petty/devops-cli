## ADDED Requirements

### Requirement: A verification pass follows the gates
When the caller gives a verifier, the planner SHALL make one verification call for each plan after the plan passes `check_proposal` and `validate_change`, and before the job opens the draft pull request. The verifier SHALL be the client of the task slot `ai.tasks.verification`. The request SHALL hold the issue, the plan, and the capped start of each file that the plan cites. The pass SHALL NOT merge a pull request and SHALL NOT mark one ready.

#### Scenario: A plan that passes the gates
- **WHEN** a plan passes the gates and the verifier finds nothing
- **THEN** the verifier gets one request with the issue, the plan and the cited files, and the job opens the draft pull request

#### Scenario: A long cited file
- **WHEN** a plan cites a file with more tokens than `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS`
- **THEN** the request holds only the first tokens of that file

#### Scenario: A plan that fails the gates
- **WHEN** the gates refuse a plan twice
- **THEN** the verifier gets no request

#### Scenario: No pull request is merged or marked ready
- **WHEN** the pass ends with findings
- **THEN** the draft pull request stays a draft and the job makes no merge call

### Requirement: A finding has one of the nine defect types
A verification reply SHALL hold findings, and each finding SHALL have a `type` that is one of `missing_path`, `false_premise`, `spec_delta_wrong`, `verify_form`, `task_order`, `criterion_dropped`, `ignores_existing_code`, `contrived_test` and `other`, a place, a problem and a quote. The prompt of the pass SHALL name the same nine types.

#### Scenario: An unknown type
- **WHEN** the verifier names a finding type outside the nine types on both tries
- **THEN** the item stops with the class `StructuredOutputValidationError` and the job opens no pull request

#### Scenario: The prompt and the schema agree
- **WHEN** the prompt of the pass is read
- **THEN** it names each of the nine types and no other type

### Requirement: An evidence-backed finding returns the plan once
A finding of type `missing_path`, `false_premise` or `ignores_existing_code` whose quote is in the issue, the plan or a cited file SHALL return the plan to the planner once, with the finding as the problem. The revised plan SHALL pass the gates and the verification again. The planner SHALL NOT return a plan for a second time.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan and the cited files
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the revised plan gets a `missing_path` finding with a quote
- **THEN** the planner makes no third request and the finding goes into the comment

### Requirement: Other findings go into the comment
The job SHALL list each finding that does not return the plan in the comment that names the draft pull request, with its type, place, problem and quote. The text of a finding SHALL be on one line, with a handle, a link or a reference to another repository in a code span. The job SHALL open the draft pull request.

#### Scenario: A contrived test finding
- **WHEN** the verifier returns a `contrived_test` finding
- **THEN** the comment lists the finding and the draft pull request is open

#### Scenario: No finding
- **WHEN** the verifier returns no finding
- **THEN** the comment holds no findings section
