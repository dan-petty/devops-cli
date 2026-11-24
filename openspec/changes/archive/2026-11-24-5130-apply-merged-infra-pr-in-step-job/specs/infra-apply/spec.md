# infra-apply Specification Delta

## ADDED Requirements

### Requirement: Level gate for infra apply step job
The `infra-apply` step job SHALL refuse an infra repo whose agent access level is below `safe`.

#### Scenario: Refuse plan level
- **WHEN** a merged pull request of an infra repo at level `none` or `plan` starts the step job
- **THEN** the job writes no plan, makes no apply, and reports that the level is too low.

### Requirement: Plan before apply in step job
The `infra-apply` step job SHALL save an infra plan for the merge commit before it applies that plan.

#### Scenario: Plan the merge commit
- **WHEN** the step job starts for a merged pull request at level `safe` or `full`
- **THEN** the job saves the plan for the merge commit and calls `apply_saved_plan` only with that plan.

### Requirement: Apply only an ok plan
The `infra-apply` step job SHALL apply only an infra plan that ended `ok`.

#### Scenario: Failed plan
- **WHEN** the plan for the merge commit ended `failed`
- **THEN** the job makes no apply and reports the failed plan.

### Requirement: Stop before own node and control-plane node
The `infra-apply` step job SHALL stop before a disruptive host that is its pod node or the control-plane node and report a workstation run.

#### Scenario: Own node in the plan
- **WHEN** the plan has a disruptive host that is the node of the step job pod or the control-plane node
- **THEN** the job stops before that host, uncordons no node, and posts a message that names the host and the workstation run.

### Requirement: One comment per merge
The `infra-apply` step job SHALL post exactly one comment on the merged pull request for each merge.

#### Scenario: Comment with result and audit record
- **WHEN** the step job finishes
- **THEN** it posts one comment with the result and the audit record, with a hidden marker keyed by the merge commit.

#### Scenario: Deduplicate comments
- **WHEN** the step job runs again for the same merge commit
- **THEN** it edits the existing comment instead of posting a new one.

### Requirement: One issue per failure
The `infra-apply` step job SHALL open or update one issue in the infra repo when an apply fails or stops.

#### Scenario: Issue on failure
- **WHEN** the step job fails or stops
- **THEN** it opens or updates an issue in the infra repo with the failure details.
