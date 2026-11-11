## ADDED Requirements

### Requirement: A failed check outside the repair scope gets no fix turn
The job SHALL stop the item as Blocked with no model request when the log of a failed check of the pull request names no path of the repair scope. The scope SHALL hold each path that the plan names in the code spans of its groups, and each file of the change folder. The stop reason SHALL name the check and the scope.

#### Scenario: A workflow check outside the plan fails after the push
- **WHEN** the check `Deploy Preview` fails and its log names no path of the repair scope
- **THEN** the job runs no fix step, the item is Blocked, and the reason names `Deploy Preview` and the paths of the scope

#### Scenario: A check on a path of the plan fails
- **WHEN** the check `Static Analysis` fails and its log names `src/app.py`, which the plan names
- **THEN** the job runs a fix step, at most `repair_rounds` times
