## ADDED Requirements

### Requirement: The job leaves out a Staged item whose draft holds the label plan/needs-fix
The implement selection SHALL leave out a Staged item while its open draft pull request holds the label `plan/needs-fix`, with a reason that names the label and the pull request. The row `implement` of the Service SHALL log such an item once for each draft and record the draft in `implement.needs_fix`. The selection SHALL take the item again when the label is gone, and a round that judges the item and does not leave it out for the label SHALL clear the mark.

#### Scenario: The draft holds the label
- **WHEN** the open draft of a Staged item holds the label `plan/needs-fix`
- **THEN** `plan_implement` returns no target for the item, and its reason names the label and the pull request

#### Scenario: The Service logs the item once
- **WHEN** two rounds of the row `implement` judge the item while its draft holds the label
- **THEN** no round creates a Job, the log holds one line for the item, and `implement.needs_fix` holds the number of the draft

#### Scenario: The label is gone
- **WHEN** a round judges the item after the label was removed from its draft
- **THEN** the round creates the Job of the item and clears `implement.needs_fix`

#### Scenario: The label comes back
- **WHEN** the label comes back on the draft after a round judged the item without it
- **THEN** the next round logs the item again and creates no Job
