## MODIFIED Requirements

### Requirement: The job leaves out an item whose plan fails the check
The implement selection SHALL run `check_proposal` on the plan of a Staged or Planned item before it returns a target, and it SHALL leave the item out with the first problem as its reason when the check returns problems. When the check returns no problem, the selection SHALL run `validate_change` on the same change files with the tool that `openspec_tool()` yields, and it SHALL leave the item out with the first issue of the report as its reason when the validation returns a problem. It SHALL skip the validation when `openspec_tool()` yields None, and it SHALL leave the item out with the first line of the error when `validate_change` raises. One call of `plan_implement` SHALL enter the `openspec_tool()` context once for the whole run. It SHALL run no plan check on a Staged item whose branch head holds the archived change of the issue and no active one, because the job archives a change only after the plan passed the check.

#### Scenario: A Staged item with a placeholder task
- **WHEN** The branch of a Staged item holds a plan with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target for the item and its reason holds the first problem.

#### Scenario: A Planned item with a placeholder task
- **WHEN** The default branch holds the plan of a Planned item with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target and makes no branch for the item.

#### Scenario: A plan that passes the check
- **WHEN** The plan of the item passes every `check_proposal` gate and the OpenSpec validation finds no issue.
- **THEN** `plan_implement` returns the item as a target.

#### Scenario: A plan with two problems
- **WHEN** The plan returns two or more problems and the job leaves the item out.
- **THEN** The reason of the item holds the first problem and no later problem.

#### Scenario: A plan that the reader refuses
- **WHEN** The change folder of the item is missing or holds a file that the reader cannot parse.
- **THEN** `plan_implement` returns no target, makes no branch, and its reason names the read problem.

#### Scenario: A test path that no file holds
- **WHEN** The verification command of group 1 names a test path that the staged commit does not hold and that no group creates.
- **THEN** `plan_implement` returns no target for the item, and its reason names the path, so no run starts to amend the path.

#### Scenario: A branch whose change is archived
- **WHEN** The branch head of a Staged item holds `openspec/changes/archive/<date>-1-<slug>/` and no `openspec/changes/1-*/`, and a person comments `implement: retry` after a stop
- **THEN** `plan_implement` returns the item as a target

#### Scenario: A plan that `check_proposal` accepts and the validation refuses
- **WHEN** The plan of an item passes every `check_proposal` gate and `openspec validate --strict` reports an issue.
- **THEN** `plan_implement` returns no target for the item, and its reason holds the first issue of the report and no later one.

#### Scenario: No `openspec` binary on PATH
- **WHEN** `openspec_tool()` yields None.
- **THEN** `plan_implement` leaves the item out only for a problem of `check_proposal`, and returns it as a target when the check finds none.

#### Scenario: One tool context for a plan run
- **WHEN** `plan_implement` judges two items.
- **THEN** `openspec_tool()` is entered once for the run.

#### Scenario: A validation that cannot run
- **WHEN** `validate_change` raises `RoadmapStageError` or `ToolExecutionError` for the plan of an item.
- **THEN** `plan_implement` leaves that item out with the first line of the error as its reason and returns the other items as targets.
