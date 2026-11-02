## ADDED Requirements

### Requirement: Criteria mapping in the stage reply
The stage reply SHALL hold a `criteria` list in which each entry gives the text of one acceptance criterion of the issue and either the number of the group that delivers it or `pending-person` with a reason.

#### Scenario: Every criterion is mapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list holds an entry for each, with a group number or `pending-person` and a reason
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: One of three criteria is unmapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list maps only two
- **THEN** `check_proposal` returns a problem that names the unmapped criterion

### Requirement: Criteria section in tasks.md
The `tasks.md` of a staged plan SHALL hold a Criteria section that lists each acceptance criterion of the issue with the number of the group that delivers it, or `pending-person` with the reason.

#### Scenario: Staged plan shows the mapping
- **WHEN** A plan is rendered with criteria mapped to groups
- **THEN** `tasks.md` holds a Criteria section with one line for each criterion and its delivering group number or `pending-person` with the reason
