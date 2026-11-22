## ADDED Requirements

### Requirement: The open step and the ready check measure one text
The open step, the form check of `devops pr create`, the ready check and the plan check SHALL give the body limit the text of one function: the text above the line that the form takes as `Closes`, or as `Plans` in a plan body, with the whitespace at its start and at its end removed. A body that starts with a blank line SHALL get the same length at each check.

#### Scenario: A body that starts with a blank line at the limit
- **WHEN** a body starts with a blank line, then a text of 1,000 characters, `Closes #5020` and a `Change:` line
- **THEN** the open step and the ready check find no problem, and the measured text is the text of 1,000 characters

#### Scenario: A body that starts with a blank line over the limit
- **WHEN** a body starts with a blank line, then a text of 1,001 characters, `Closes #5020` and a `Change:` line
- **THEN** the open step and the ready check each find one problem, and its text names the length 1001

#### Scenario: A plan body that starts with a blank line
- **WHEN** a plan body starts with a blank line, then a text of 1,000 characters, the `Plans` line and the `Change:` line
- **THEN** the plan form check and the plan check find no problem of the length

## MODIFIED Requirements

### Requirement: The rules cut no text
The builders of the title and the body SHALL return the text as given, or raise `ValidationError` that names every problem. They SHALL NOT shorten a text, and no text they return ends with `...` because of a cut. The text they return SHALL pass the check of the same rules.

#### Scenario: A summary that is too long
- **WHEN** a title is built with a summary of 90 characters
- **THEN** the builder raises `ValidationError`, and its message names the limit 60
- **AND** it returns no title

#### Scenario: A why that is too long
- **WHEN** a body is built with a text of more than 1,000 characters above `Closes`
- **THEN** the builder raises `ValidationError` whose message tells to shorten the text above `Closes`

#### Scenario: The body built passes the check
- **WHEN** a body is built from a text, an issue, a folder and two attribution paragraphs
- **THEN** the body is the text, `Closes #<issue>`, the `Change:` line and the two paragraphs, each after a blank line
- **AND** the check of the body finds no problem

### Requirement: devops pr describe refuses and prints nothing
`devops pr describe` SHALL exit 1, print every problem to stderr, and print nothing to stdout when: the summary breaks a rule of the title; the scope of the issue has no label; the text above `Closes` has more than 1,000 characters; the proposal has no section `Why`; the text of the proposal holds a closing keyword for an issue; the issue has no change folder, or more than one; or the number is no item of the roadmap. It SHALL NOT cut a text.

#### Scenario: A summary of 61 characters or more
- **WHEN** the summary has more than 60 characters
- **THEN** the exit status is 1, stdout is empty, and stderr names the limit 60

#### Scenario: A placeholder summary
- **WHEN** the summary is `placeholder`
- **THEN** the exit status is 1 and stderr says that the summary is a placeholder

#### Scenario: A scope with no label
- **WHEN** the issue is titled `feat(zzz-unknown): a change` and the labels do not declare `scope/zzz-unknown`
- **THEN** the exit status is 1 and stderr names `scope/zzz-unknown`

#### Scenario: A why over the limit
- **WHEN** `--why` gives a text of more than 1,000 characters
- **THEN** the exit status is 1, stdout is empty, and stderr tells to shorten the text above `Closes`

#### Scenario: A proposal with no why
- **WHEN** the proposal has no section `Why`
- **THEN** the exit status is 1 and stderr names the proposal and the option `--why`

#### Scenario: A why that closes an issue
- **WHEN** the section `Why` says `This closes #7`
- **THEN** the exit status is 1 and stderr names the closing keyword

#### Scenario: No change folder
- **WHEN** the issue has no folder under `openspec/changes/` and none in the archive
- **THEN** the exit status is 1 and stderr names the issue

#### Scenario: Not an item
- **WHEN** the number is no item of the roadmap
- **THEN** the exit status is 1 and stderr says that the issue is no item
