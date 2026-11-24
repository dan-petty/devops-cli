## ADDED Requirements

### Requirement: A test-first stop is a plan defect
The classifier SHALL give `FailureClass.PLAN_DEFECT` to a stop whose text matches `implement_stop_no_test_file`, `implement_stop_base_passes` or `implement_stop_base_errors`. The implement step SHALL give `FailureClass.PLAN_DEFECT` to each test-first stop.

#### Scenario: Behavior group changes no test file
- **WHEN** a behavior group changes no file under `tests/`
- **THEN** the failure class is `plan_defect` and the action is `amend`

#### Scenario: Tests pass on base commit
- **WHEN** tests of a behavior group pass on the base commit and repair rounds are exhausted
- **THEN** the failure class is `plan_defect` and the action is `amend`

#### Scenario: Tests error on base commit
- **WHEN** tests of a behavior group error on the base commit and repair rounds are exhausted
- **THEN** the failure class is `plan_defect` and the action is `amend`
