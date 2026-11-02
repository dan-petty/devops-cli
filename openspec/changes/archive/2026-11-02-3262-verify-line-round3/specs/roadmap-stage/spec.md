## ADDED Requirements

### Requirement: A text of the proposal, the design and the spec delta stays on one line
The `why`, `what_changes`, `feasibility` and `existing_tool` of the reply, the texts of its decisions and rejected alternatives, and the `purpose`, the names, the texts and the scenario lines of its spec deltas, SHALL be written on one line. A text that is written at the start of a line SHALL start with no mark of markdown: a heading, a quote, a list marker, a box, a rule, a fence or a comment. The reply that breaks the rule fails the schema.

#### Scenario: A removed section in a requirement
- **WHEN** the `text` of a requirement holds a line break, a heading `## REMOVED Requirements` and a requirement
- **THEN** the `spec.md` of the delta holds the headings Purpose, ADDED Requirements and the one requirement, and no REMOVED section

#### Scenario: A text that starts with a heading
- **WHEN** the `why` of the reply is `## REMOVED Requirements`
- **THEN** the reply fails the schema, and the error says that the text starts with a mark of markdown

#### Scenario: A line break in a bullet
- **WHEN** an item of `feasibility` holds a blank line and a heading
- **THEN** the item is one line

### Requirement: A verify command keeps its spaces
The `verify` of a task group SHALL be written on one line by joining its lines with one space, and SHALL keep every other space of the command.

#### Scenario: Two spaces in a word
- **WHEN** the `verify` is `! git grep -n 'a  b'` and a line break and `src/`
- **THEN** the `verify` of the group is `! git grep -n 'a  b' src/`

## MODIFIED Requirements

### Requirement: A text of a group stays on one line
The `title`, `test`, `implementation`, `documentation`, `verify` and `process` of a task group, and the `criterion` and the `reason` of a criterion, SHALL be written to `tasks.md` on one line, and a text set after validation SHALL be validated again. A line break in one of them SHALL add no line, no task, no group and no `Verification:` line.

#### Scenario: A line break and a command
- **WHEN** the `implementation` of a group holds a line break and a line `- Verification: ` with a command
- **THEN** the `verification_commands` of the parsed group are the `verify` of the group and the check of the documents, and no more

#### Scenario: A line break in a title
- **WHEN** the `title` of a group holds a blank line and a line `- [ ] 9.9 Extra`
- **THEN** `tasks.md` holds one group and the task list is that of the group

#### Scenario: A line break in the reason of a criterion
- **WHEN** the `reason` of a `pending-person` criterion holds a line `## 2. Extra`
- **THEN** `tasks.md` holds one group

#### Scenario: Any line terminator
- **WHEN** a text of a group holds a heading after any character that ends a line in markdown or in Python, such as `\r`, `\x85` or U+2028
- **THEN** `tasks.md` holds one group, and the text holds one space in place of the character

#### Scenario: A text set after validation
- **WHEN** the `implementation` of a validated group is set to a text with a line break and a `Verification:` line
- **THEN** the text is on one line, and the group renders no extra command

### Requirement: Criteria section in tasks.md
The `tasks.md` of a staged plan SHALL hold a `## Criteria` section before `## Workflow follow-up`. It SHALL list each criterion as a bullet with no checkbox, and each bullet SHALL start with a fixed word: `Group <n>:` and the criterion, or `Pending person:`, the criterion and the reason. A criterion that reads as a heading or a task SHALL add no group and no task.

#### Scenario: Staged plan shows the mapping
- **WHEN** A plan is rendered with criteria mapped to groups
- **THEN** `tasks.md` holds a `## Criteria` section with one line for each criterion, as `Group <n>: <criterion>` or `Pending person: <criterion>, <reason>`

#### Scenario: A plan with no criterion has no section
- **WHEN** A plan is rendered with an empty `criteria` list
- **THEN** `tasks.md` holds no `## Criteria` section

#### Scenario: A criterion that reads as a heading
- **WHEN** a criterion of the issue is `## 2. Cleanup`
- **THEN** the gate accepts the entry that copies it, and `tasks.md` holds the group 1 only

### Requirement: A verify command holds no backtick
`form_problems` SHALL give a problem for a `verify` command that holds a backtick, and the problem SHALL say that it holds a backtick. A command that also has a wrong form SHALL get the problem of its form in the same run.

#### Scenario: A backtick in a command
- **WHEN** the `verify` of a group is ``uv run devops ci test `x` ``
- **THEN** `form_problems` gives one problem, and it says that the command holds a backtick

#### Scenario: A backtick and a wrong form
- **WHEN** the `verify` of a group is ``pytest `x` ``
- **THEN** `form_problems` gives two problems: the backtick, and the form to use
