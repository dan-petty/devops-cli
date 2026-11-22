## ADDED Requirements

### Requirement: The open step and the ready check measure one text
The open step, the form check of `devops pr create`, the ready check and the plan check SHALL give the body limit the text of one function. That text SHALL end at the first line that is `Closes #<issue>`, or `Plans #<issue>` in a plan body, when the whitespace at the ends of that line is removed. The whitespace at the start and at the end of the text SHALL NOT count. A body that starts with a blank line SHALL get the same length at each check.

#### Scenario: A body that starts with a blank line at the limit
- **WHEN** a body starts with a blank line, then a text of 1,000 characters, `Closes #5020` and a `Change:` line
- **THEN** the open step and the ready check find no problem, and the measured text is the text of 1,000 characters

#### Scenario: A body that starts with a blank line over the limit
- **WHEN** a body starts with a blank line, then a text of 1,001 characters, `Closes #5020` and a `Change:` line
- **THEN** the open step and the ready check each find one problem, and its text names the length 1001

#### Scenario: A plan body that starts with a blank line
- **WHEN** a plan body starts with a blank line, then a text of 1,000 characters, the `Plans` line and the `Change:` line
- **THEN** the plan form check and the plan check find no problem of the length

#### Scenario: A Plans line with a space at its end
- **WHEN** a plan body has a text of 1,000 characters, then the line `Plans #<issue>` with a space at its end, and the `Change:` line
- **THEN** the plan check finds no problem of the length, and the measured text is the text of 1,000 characters

#### Scenario: A Closes line with a space at its end
- **WHEN** a body has a text of 1,000 characters, then `Closes #5020` with a space at its end, and a `Change:` line
- **THEN** the open step and the ready check find no problem, and the measured text is the text of 1,000 characters

### Requirement: Each reader takes the marker line by one rule
The form check of `devops pr create`, the open step, the ready check, the measure of the body limit, the plan check and the grounding of a plan SHALL take a line as the `Closes` line or the `Plans` line by one rule. The rule takes a line that is `Closes #<issue>` or `Plans #<issue>` when the whitespace at its ends is removed. The issue SHALL have ASCII digits only, because GitHub links no other digit. The form check SHALL count each line that the rule takes, so a second such line is a problem.

#### Scenario: A padded Plans line above the Plans line
- **WHEN** a plan body has a text of 58 characters, then `Plans #5020` with a space at its end, a text of 2,000 characters, the line `Plans #5020` and the `Change:` line
- **THEN** the plan form check finds one problem, and its text names the single line `Plans #5020`

#### Scenario: A Plans line with whitespace at its ends
- **WHEN** a plan body has the line `Plans #3215` with a space at its end, or with a tab at its start
- **THEN** the plan form check, the plan check, the grounding of a plan and the measure each take that line as the `Plans` line

#### Scenario: A Plans line with digits that are not ASCII
- **WHEN** a plan body has the line `Plans #` with the full-width digits of 3215
- **THEN** no reader takes that line as the `Plans` line, and the plan form check finds the problem of the missing `Plans` line

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

### Requirement: The body ends with Closes and the Change line
The body of a delivery (a pull request whose title is no plan) SHALL be, in this order: a text of at least 20 characters (what the change does, and why), the line `Closes #<issue>`, the line `Change:` with the folder of the same issue in a code span, and then the attribution lines, if any. The text above `Closes`, with the whitespace at its start and at its end removed, SHALL have at most 1,000 characters. The lines after `Change:` SHALL have at most 400 characters.

#### Scenario: A body in the form
- **WHEN** the body is a sentence, `Closes #3198` and a `Change:` line for issue 3198
- **THEN** the rules find no problem

#### Scenario: The folder of the change
- **WHEN** the `Change:` line names `openspec/changes/3198-form/` or `openspec/changes/archive/2026-11-02-3198-form/`
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

#### Scenario: A body at the limit above Closes
- **WHEN** the text above `Closes` has 1,000 characters and the `Closes` and `Change:` lines add 120 characters
- **THEN** the rules find no problem

#### Scenario: A body over the limit
- **WHEN** the text above `Closes` has 1,001 characters and the `Closes` and `Change:` lines add 120 characters
- **THEN** the rules find one problem, and its text names the text above `Closes`, the length 1001 and the limit

### Requirement: The plan body limit measures the text above Plans
The plan form check SHALL measure only the text above the `Plans` line, with the whitespace at its start and at its end removed, against the 1,000-character limit, and the problem of a body over the limit SHALL name that text. The room of a plan text SHALL be the whole limit, so a text of 1,000 characters builds a plan body.

#### Scenario: A plan body at the limit above Plans
- **WHEN** the text above `Plans` has 1,000 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the plan form check reports no problem, and the room of the plan text is 1,000 characters

#### Scenario: A plan body over the limit above Plans
- **WHEN** the text above `Plans` has 1,001 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the plan form check reports one problem, and its text names the text above `Plans`, the length 1001 and the limit

#### Scenario: A plan body in the room of its text
- **WHEN** the builder gets a text of exactly the room that the plan form gives
- **THEN** it returns the body with no problem, and one more character is refused
