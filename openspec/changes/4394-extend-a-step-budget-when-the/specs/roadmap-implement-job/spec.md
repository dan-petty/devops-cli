## ADDED Requirements

### Requirement: The comments and the record show the extension of a step budget
The record `implement.spend` SHALL hold, for each step that got the one extension of its token budget, the old budget, the new budget, the counts that gave it and whether the ceiling cut it. The ready comment and the stop comment of the item SHALL list each such step of the run, the earlier Jobs included, with the budgets and the counts only. A run with no extension SHALL show no such list.

#### Scenario: A ready item with an extended step
- **WHEN** group 1 got an extension from 100 to 150 input tokens with 2 successful edits and 0 refused commands, and the item reaches a ready pull request
- **THEN** the ready comment lists group 1 with 100 to 150 input tokens and those counts, and the record holds the extension of group 1 and none for group 2

#### Scenario: A stop after an extension
- **WHEN** group 1 got an extension and then reached its new budget
- **THEN** the stop comment names the class `limit_reached`, lists the extension of group 1 and gives the reason that names the extension

#### Scenario: No extension
- **WHEN** no step of the run got an extension
- **THEN** the comment of the item lists no budget extension
