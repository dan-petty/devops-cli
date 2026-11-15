# Tasks

## 1. Remove only the label that the drift row added

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/plan_drift.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage/plan_drift.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_drift.py`.

- [x] 1.1 Write tests: a label of the stage review stays when the plan passes, a label held before the drift stays, an open finding of the plan comment keeps the label, the row removes the label that it added and marks its comment `cleared`, and a cleared comment leaves a later label
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py` fails on the base
- [x] 1.2 Add `DriftClaim`, the claim line of the drift comment, the comment of a passing plan and the rule that removes the label only for the claim `added`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py`

## Criteria

- Group 1: ### Requirement: Remove the label after a passing check The Service SHALL remove the label `plan/needs-fix` from a plan pull request when a later drift check reports no problem, only when the drift row added the label and the last plan comment of the item lists no open finding.
- Group 1: ### Requirement: Mark a passing plan in the drift comment The Service SHALL change the drift comment of a plan pull request to the claim `cleared` when a later drift check reports no problem.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
