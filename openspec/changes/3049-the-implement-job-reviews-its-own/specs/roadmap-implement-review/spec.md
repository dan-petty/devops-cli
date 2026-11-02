## Purpose
The implement job reviews its own diff and its plan conformance before it marks the pull request ready, within a stated call budget.

## ADDED Requirements

### Requirement: Review runs before the ready mark
The implement job SHALL run `devops review` on the item's diff and a plan-conformance check after the last task group and before it marks the pull request ready.

#### Scenario: Review runs after the last task group
- **WHEN** the implement job finishes the last task group of the item
- **THEN** the job runs `devops review` on the diff and the plan-conformance check, and no ready mark happens before both return

#### Scenario: Seeded high-severity finding is repaired
- **WHEN** a replay test seeds a high-severity finding in the diff and the fix step clears it
- **THEN** the job re-runs the review and marks the pull request ready

### Requirement: A surviving high-severity finding blocks the ready mark
The implement job SHALL run one repair round for a high-severity finding, and MUST NOT mark the pull request ready while a high-severity finding stays open.

#### Scenario: Seeded high-severity finding survives the repair round
- **WHEN** a replay test seeds a high-severity finding that the fix step does not clear
- **THEN** the job stops the item, records the reason and leaves the pull request a draft

#### Scenario: Checks pass but a review finding stays open
- **WHEN** every check passed and the review still holds an open high-severity finding
- **THEN** the pull request stays a draft

### Requirement: The comment lists every finding with its disposition
The implement job SHALL post each review finding in the pull request comment with its disposition: repaired, suppressed or blocking.

#### Scenario: Findings listed with their disposition
- **WHEN** the review completes with one or more findings
- **THEN** the pull request comment holds one line for each finding with its location, its severity and its disposition

### Requirement: The review call budget is stated and enforced
The implement job SHALL limit the review runs per item to `roadmap.implement.review_runs` and MUST stop the review with the budget reason when the limit is reached.

#### Scenario: Budget is spent
- **WHEN** the review reaches the number of runs of `roadmap.implement.review_runs` with a high-severity finding still open
- **THEN** the job stops the review and blocks the item with the reason that the review budget was spent

#### Scenario: Budget is one initial run and one re-run
- **WHEN** the default settings load
- **THEN** `roadmap.implement.review_runs` is 2

### Requirement: The ready mark waits for the checks and the review
The implement job SHALL mark the pull request ready only when every check passed and the review holds no unresolved high-severity finding.

#### Scenario: Both gates pass
- **WHEN** every check passed and the review holds no unresolved high-severity finding
- **THEN** the job marks the pull request ready and sets Status In Review
