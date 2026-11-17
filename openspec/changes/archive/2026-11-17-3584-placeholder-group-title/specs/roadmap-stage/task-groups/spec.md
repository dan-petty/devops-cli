## ADDED Requirements

### Requirement: Refusal of a placeholder group title
`content_problems` and `group_title_problems` SHALL refuse a plan or task text when any task group title is a placeholder word. The rule SHALL call `is_placeholder` on the title only and SHALL NOT apply `PLAN_FIELD_MIN_CHARS` to it.

#### Scenario: A placeholder group title is refused
- **WHEN** a plan holds a task group with the title `x`
- **THEN** `content_problems` returns a problem that names the group and its title

#### Scenario: A short real title is accepted
- **WHEN** a plan holds a task group with the title `Archive`
- **THEN** `content_problems` returns no problem for that group title

#### Scenario: Direct call of the shared helper
- **WHEN** a test calls `group_title_problems` with the text `## 1. x`
- **THEN** the helper returns one problem that names the group `1` and its title `x`
