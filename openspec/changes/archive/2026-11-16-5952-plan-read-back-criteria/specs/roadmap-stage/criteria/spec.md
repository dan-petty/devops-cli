## ADDED Requirements

### Requirement: A criterion entry holds what its line holds
`StageCriterion` SHALL fold its `criterion` and its `reason` on one line with the fold of the writer (`one_line`), and an entry with a group number SHALL keep no reason. So the plan reader SHALL read back each entry of a rendered plan with the same criterion, group and reason.

#### Scenario: A group entry with a reason
- **WHEN** the reply maps "A test: a draft with a failed check backs off, and the test holds the interval." to group 1 with the reason `""` or "Group 1 adds the test."
- **THEN** the entry has no reason, and `read_back_problems` gives no problem for `criteria`

#### Scenario: A criterion with a line break
- **WHEN** an entry of the reply holds a criterion with a line break, two spaces or U+FEFF between its words
- **THEN** the entry holds the criterion on one line with one space between the words, as the line of `## Criteria` does
