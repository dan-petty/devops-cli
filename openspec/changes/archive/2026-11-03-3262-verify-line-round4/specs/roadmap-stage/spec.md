## ADDED Requirements

### Requirement: A split reply is checked for the form of its commands
The job SHALL check the groups of a split reply for the form of their `verify` commands, as it checks the groups of a plan, and SHALL send a reply with a problem back to the model once.

#### Scenario: A split group with two commands
- **WHEN** a split group has a `verify` of ``uv run devops ci test tests/x.py` and `git push origin HEAD``
- **THEN** the reply goes back to the model with the `verify` problem, and the model is asked once more

## MODIFIED Requirements

### Requirement: A text of the proposal, the design and the spec delta stays on one line
The `why`, `what_changes`, `feasibility` and `existing_tool` of the reply, the texts of its decisions and rejected alternatives, and the `purpose`, the names, the texts and the scenario lines of its spec deltas, SHALL be written on one line, and U+FEFF SHALL count as white space. A text at the start of a line SHALL start with no mark of markdown: a heading, a quote, a list marker, a box, a rule, a fence or an HTML tag. The reply that breaks the rule fails the schema.

#### Scenario: A removed section in a requirement
- **WHEN** the `text` of a requirement holds a line break, a heading `## REMOVED Requirements` and a requirement
- **THEN** the `spec.md` of the delta holds the headings Purpose, ADDED Requirements and the one requirement, and no REMOVED section

#### Scenario: A text that starts with a heading
- **WHEN** the `why` of the reply is `## REMOVED Requirements`
- **THEN** the reply fails the schema, and the error says that the text starts with a mark of markdown

#### Scenario: A line break in a bullet
- **WHEN** an item of `feasibility` holds a blank line and a heading
- **THEN** the item is one line

#### Scenario: A mark after U+FEFF
- **WHEN** the `purpose` of a spec is U+FEFF, `##`, U+FEFF and `REMOVED Requirements`
- **THEN** the reply fails the schema

#### Scenario: An HTML tag
- **WHEN** the `existing_tool` of the reply starts with `<pre>`
- **THEN** the reply fails the schema
