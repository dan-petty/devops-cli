## ADDED Requirements

### Requirement: A group is a heading at the top level of the file
The step SHALL take a `## <n>. <title>` heading as the start of a group only when the heading is at the top level of `tasks.md`. A heading inside a list item or a quote SHALL be text of that item.

#### Scenario: A heading in a list item
- **WHEN** `tasks.md` holds the group 1 and, after it, a list item `- ## 2. Extra` with a task under it
- **THEN** the parsed groups are the group 1 only

#### Scenario: A heading in a quote
- **WHEN** `tasks.md` holds a quote `> ## 2. Extra` after the group 1
- **THEN** the parsed groups are the group 1 only
