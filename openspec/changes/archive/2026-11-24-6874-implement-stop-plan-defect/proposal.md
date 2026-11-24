# Proposal: #6874

## Why
The implement job stops when a behavior group changes no test file or when its tests do not fail on base.
Currently, these stops default to the failure class `ci_infra` with the retry action.
`ci_infra` represents an infrastructure outage.
A group with no test file or an invalid test is a defect of the plan or agent work.
Retrying the job does not resolve a plan defect and can repeat the stop.

## What Changes
Assign `FailureClass.PLAN_DEFECT` to test-first stops in `src/devops_cli/roadmap/implement/implement_step.py`:
- `implement_stop_no_test_file`
- `implement_stop_base_passes`
- `implement_stop_base_errors`
Update `classify_failure` in `src/devops_cli/roadmap/failure.py` to classify these stop messages as `FailureClass.PLAN_DEFECT`.
Ensure `_repair_ask` permits repair rounds for replay failures that carry repair paths.

## Capabilities
Test-first implement stops carry the `plan_defect` failure class.
The classifier recognizes test-first stop texts as `plan_defect`.
The Service does not clear test-first stops as infrastructure outages.

## Impact
Items that stop due to test-first errors receive the `plan_defect` class and `amend` action instead of repeated retries.
No breaking changes to public APIs.

## Feasibility
Verified stop points in `src/devops_cli/roadmap/implement/implement_step.py` and `src/devops_cli/roadmap/failure.py`.
Verified that `FailureClass.PLAN_DEFECT` maps to `FailureAction.AMEND` in `ACTION_BY_CLASS`.

## Existing Tool Considered
The alternatives check in issue #6874 records verdict `none`.
The classification requires project-internal mapping between implement stop messages and failure classes.
Written cost: about 10,000 tokens and 1 hour elapsed.
