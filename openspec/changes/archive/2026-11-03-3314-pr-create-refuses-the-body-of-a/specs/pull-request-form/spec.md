## MODIFIED Requirements

### Requirement: The body ends with Closes and the Change line
The body of a delivery (a pull request whose title is no plan) SHALL be, in this order: a text of at least 20 characters (what the change does, and why), the line `Closes #<issue>`, the line `Change:` with the folder of the same issue in a code span, and then the attribution lines, if any. The text, `Closes` and `Change:` SHALL have at most 1,000 characters together, and the lines after them at most 400.

#### Scenario: A body in the form
- **WHEN** the body is a sentence, `Closes #3198` and a `Change:` line for issue 3198
- **THEN** the rules find no problem

#### Scenario: The folder of the change
- **WHEN** the `Change:` line names ``openspec/changes/3198-form/`` or ``openspec/changes/archive/2026-11-02-3198-form/``
- **THEN** the rules find no problem for either

#### Scenario: Attribution lines after the Change line
- **WHEN** the body in the form is followed by a `Co-Authored-By:` line
- **THEN** the rules find no problem, and those lines do not count toward the limit of 1,000 characters

#### Scenario: A missing Closes line
- **WHEN** the body has no line `Closes #<issue>`
- **THEN** the rules find one problem, and its text names the line

#### Scenario: A missing Change line
- **WHEN** the body has no line `Change:` in the form above
- **THEN** the rules find one problem, and its text names the line

#### Scenario: Two different issues in the two lines
- **WHEN** the `Closes` line names issue 3199 and the `Change:` line names issue 3198
- **THEN** the rules find one problem, and its text names both issues

#### Scenario: Closes after Change
- **WHEN** the line `Closes` comes after the line `Change:`
- **THEN** the rules find one problem, and its text says that `Closes` must come first

#### Scenario: A body over the limit
- **WHEN** the text, the `Closes` line and the `Change:` line have more than 1,000 characters
- **THEN** the rules find one problem, and its text names the length and the limit

## ADDED Requirements

### Requirement: A plan body has the Plans line and no closing keyword
`devops pr create` SHALL judge the body of a pull request whose title is `docs(openspec): plan #<issue> <summary>` by the form of a plan: exactly one line `Plans #<issue>` that names the issue of the title, no closing reference, and a `Change:` line with the active change folder of the same issue. The command SHALL NOT ask a plan body for a `Closes` line.

#### Scenario: A plan body in the form opens a draft
- **WHEN** the title is `docs(openspec): plan #3236 revise scope` and the body has the line `Plans #3236` and the line `Change: \`openspec/changes/3236-x/\``
- **THEN** the command opens a draft pull request.

#### Scenario: A plan body that closes its issue opens nothing
- **WHEN** the body of that plan has the lines `Plans #3236` and `Closes #3236`
- **THEN** the command prints that a plan closes no issue and opens nothing.

#### Scenario: A delivery title keeps the Closes rule
- **WHEN** the title is `feat(pr): check the form` and the body has no `Closes` line
- **THEN** the command prints that the body has no `Closes` line and opens nothing.
