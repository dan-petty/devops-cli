## ADDED Requirements

### Requirement: The plan body limit measures the text above Plans
The plan form check SHALL measure only the text above the `Plans` line, with its trailing blank lines removed, against the 1,000-character limit, and the problem of a body over the limit SHALL name that text. The room of a plan text SHALL be the whole limit, so a text of 1,000 characters builds a plan body.

#### Scenario: A plan body at the limit above Plans
- **WHEN** the text above `Plans` has 1,000 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the plan form check reports no problem, and the room of the plan text is 1,000 characters

#### Scenario: A plan body over the limit above Plans
- **WHEN** the text above `Plans` has 1,001 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the plan form check reports one problem, and its text names the text above `Plans`, the length 1001 and the limit

#### Scenario: A plan body in the room of its text
- **WHEN** the builder gets a text of exactly the room that the plan form gives
- **THEN** it returns the body with no problem, and one more character is refused

## MODIFIED Requirements

### Requirement: The body ends with Closes and the Change line
The body of a delivery (a pull request whose title is no plan) SHALL be, in this order: a text of at least 20 characters (what the change does, and why), the line `Closes #<issue>`, the line `Change:` with the folder of the same issue in a code span, and then the attribution lines, if any. The text above `Closes`, with its trailing blank lines removed, SHALL have at most 1,000 characters. The lines after `Change:` SHALL have at most 400 characters.

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
