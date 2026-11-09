# roadmap-stage Specification Delta

## ADDED Requirements

### Requirement: Gate plan quotes the refused defect
A plan that changes a gate file SHALL quote the defective text that the gate must refuse in its Feasibility.

#### Scenario: A gate plan without the defect quote
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py`, and its Feasibility holds no code span.
- **THEN** `content_problems` returns the message that the Feasibility must quote the defective text.

### Requirement: Gate plan tests the defect on the base
A plan that changes a gate file SHALL give a test task that holds the quoted text and the phrase `fails on the base`.

#### Scenario: A gate plan with the quote and the failing test
- **WHEN** A plan changes a gate file, its Feasibility quotes the defective text, and its test task holds that text and the phrase `fails on the base`.
- **THEN** `content_problems` returns no gate defect problem.

### Requirement: Gate plan without the failing test is refused
A plan that changes a gate file and gives a test task with no `fails on the base` phrase SHALL be refused.

#### Scenario: A gate plan with the quote and no failing test
- **WHEN** A plan changes a gate file and quotes the defective text, and its test task omits `fails on the base`.
- **THEN** `content_problems` returns the message that the test task must fail on the base.

### Requirement: Gate plan states a skipped case as a non-goal
A plan whose gate test says that the rule skips a case SHALL state that non-goal in its design decisions, its rejected alternatives or its spec delta.

#### Scenario: A gate plan that skips a case without a non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and no decision, rejected alternative or spec delta text holds `non-goal`.
- **THEN** `content_problems` returns the message that the plan must state the skipped case as a non-goal.

### Requirement: Gate plan accepts a stated non-goal
A plan that states the non-goal for a skipped gate case MUST pass the non-goal rule.

#### Scenario: A gate plan with the non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and a decision text holds `non-goal`.
- **THEN** `content_problems` returns no non-goal problem.

### Requirement: The gate quote rule runs in the shared check
The gate quote rule MUST run from `content_problems`, which `check_proposal` and the replay call.

#### Scenario: The stage job and the replay report the same message
- **WHEN** A plan changes a gate file and quotes no defective text.
- **THEN** `check_proposal` and `_content_gate` both return the same `RoadmapMessages` text.

### Requirement: The gate quote rule has offline tests
`tests/roadmap/stage/test_roadmap_stage_plan.py` SHALL hold one test that refuses a gate plan with no defect quote and one test that accepts a gate plan with the quote and the failing test task.

#### Scenario: The gate quote tests run
- **WHEN** The test module runs.
- **THEN** The refusing test and the accepting test both pass.

### Requirement: A plan with no gate change is not refused
A plan that changes no gate file MUST pass the gate defect quote rule.

#### Scenario: A plan with no gate change
- **WHEN** A plan changes only `src/devops_cli/sample.py`.
- **THEN** `content_problems` returns no gate quote problem.
