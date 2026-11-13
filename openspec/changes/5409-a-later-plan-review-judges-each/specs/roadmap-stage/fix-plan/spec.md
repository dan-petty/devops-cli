## RENAMED Requirements

- FROM: `### Requirement: The step pushes a revision with fewer open findings`
- TO: `### Requirement: The step pushes a revision that fixes more findings of the head than it adds`

## MODIFIED Requirements

### Requirement: The step repairs the plan with the stage planner
The step SHALL read the plan of the head of the pull request with `read_change` and give it to the stage planner at the latest default branch. The planner SHALL get the plan as `previous` and each open finding of the review of the head and of the last plan comment as `problem`, and the revision SHALL pass the gates and the verification repair rounds of the stage job. The first review of the revision SHALL be a later review: its `earlier` key SHALL hold each open finding of the review of the head, and its `answer` key SHALL hold the text that the revision changed in the plan that passed the checks.

#### Scenario: The open findings of the stage comment
- **WHEN** the stage comment of the item lists an open finding for the pull request, and the review of the head plan has another open finding
- **THEN** the first planner request holds the head plan as `previous` and both findings in `problem`

#### Scenario: The review of the revision gets the findings of the head
- **WHEN** the review of the head plan has one open finding, and the planner answers a revision that changes the `why` of the plan
- **THEN** the request of the review of the revision holds that finding in `earlier` and the new `why` in `answer`

### Requirement: The step pushes a revision that fixes more findings of the head than it adds
When the revision of a repair is not the same plan as the plan that passed the checks, and the reviews of the revision fixed more open findings of the review of the head than they added, the step SHALL write the change folder as one commit on the latest default branch, push it to the branch of the pull request with `--force-with-lease` on the head that it read, and set the title and the body of the pull request to those of the revision. A finding of the head is fixed when it is not open in the last review of the revision. An added finding is an open finding of the last review of the revision that is no open finding of the head. The step SHALL NOT compare the counts of two independent reviews.

#### Scenario: A revision with fewer open findings
- **WHEN** the review of the head has two open findings, and the review of the revision marks one `gone` and the other `holds`
- **THEN** the branch holds one new commit whose parent is the latest default branch, the result is `revised`, and the pull request keeps `plan/needs-fix`

#### Scenario: A revision that fixes the finding of the head and opens a finding on unchanged text
- **WHEN** the review of the head has one open finding, and the review of the revision marks it `gone` and opens one finding whose quote is in text that the revision did not change
- **THEN** the new finding is advice, the step pushes the revision, the result is `cleared`, and the pull request loses `plan/needs-fix`

#### Scenario: A repair that gives the same plan
- **WHEN** the review of the head has one open finding, the planner answers the plan of the head, and the review of that plan marks the finding `gone`
- **THEN** the two plans are the same plan, because `render_change` gives the same files for both with one change name and one date, so the head of the branch does not change, the result is `unchanged`, the result line holds `success=false`, and the pull request keeps `plan/needs-fix`

### Requirement: A revision that is not better writes only the record
When no rule of a push or of a label holds, the step SHALL write nothing to GitHub except the record of the item, with the result `unchanged`. A failure before a gated plan exists, or a failure after the checks when the plan that passed them is the plan of the head, SHALL write only the record with the result `failed`.

#### Scenario: A revision that is not better
- **WHEN** the review of the revision marks the open finding of the head `holds`
- **THEN** the head of the branch does not change, the label stays, no comment is posted, and the record holds the attempt with the result `unchanged`

#### Scenario: The returns of the checks run out before the review
- **WHEN** the checks refuse the plan of the head and each new plan until the returns run out
- **THEN** the result is `failed`, the result line holds `step=gate`, the class of the failure and no `before` and no `after`, and the head of the branch does not change

#### Scenario: A failed repair
- **WHEN** the review of the head has one open finding and the checks refuse each revision of the repair until the returns run out
- **THEN** the result is `failed`, and the result line holds `before=1`, `step=plan` and the class `plan_defect`
