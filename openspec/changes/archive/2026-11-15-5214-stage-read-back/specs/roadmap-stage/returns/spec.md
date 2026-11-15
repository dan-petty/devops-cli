## MODIFIED Requirements

### Requirement: The limit of refused plans returns the item to New
The `plan_defect` or `plan_unreadable` failure that reaches `roadmap.stage.plan_defect_limit` (default 3) SHALL return the item to New in the same round. The job SHALL read the setting in each round. The job SHALL post one comment that lists in sequence, one line each and with no ping, the problems of the refused replies of the last plan and then the reason of the failure, unless the checks refused the last reply. It SHALL set New with the failure keys and clear both count keys.

#### Scenario: The third refused plan
- **WHEN** an item has 2 `plan_defect` or `plan_unreadable` failures on its body and a round of the Service refuses its plan again
- **THEN** the item is New, one comment of the stage job lists the problems of the refused replies, and the job record holds no `stage.plan_defects`

#### Scenario: A higher limit
- **WHEN** `roadmap.stage.plan_defect_limit` is 5 and an item gets its fourth `plan_defect` failure on its body
- **THEN** the item stays Ready with the count 4, and the fifth failure returns it to New with a comment that names 5

#### Scenario: A failure with no refused reply
- **WHEN** the failure at the limit holds no problem of a refused reply
- **THEN** the comment lists the reason of the failure

#### Scenario: A plan run that stops after a refused reply
- **WHEN** the checks refuse the first reply of the last plan and the second plan run stops
- **THEN** the comment lists the problem of the refused reply and then the reason of the stop

#### Scenario: A problem that names a handle
- **WHEN** a problem at the limit holds a handle and a line break
- **THEN** the comment shows the problem on one line with the handle in a code span
