## ADDED Requirements

### Requirement: The reader names an unmarked verification span
The change reader SHALL raise a diagnostic that names the group and tells the user to add `$ ` when a code span of a `Verification:` line does not start with `$ `. The diagnostic SHALL NOT say that the group has the kind `other`. A code span outside a `Verification:` line SHALL NOT raise it.

#### Scenario: An unmarked command span
- **WHEN** a `tasks.md` holds `- Verification: \`uv run devops ci test tests/sample.py\` fails on the base`
- **THEN** the reader raises a `PlanReadError` that names the group, says to add `$ `, and holds no `kind other` text

#### Scenario: A marked command span
- **WHEN** the span is `` `$ uv run devops ci test tests/sample.py` ``
- **THEN** the reader gives the group the command `uv run devops ci test tests/sample.py` and raises no marker error

#### Scenario: An inline span outside a verification line
- **WHEN** a prose line holds a code span with no `$ `
- **THEN** the reader raises no marker error
