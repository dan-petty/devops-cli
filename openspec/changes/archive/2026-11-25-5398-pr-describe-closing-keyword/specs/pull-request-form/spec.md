## ADDED Requirements

### Requirement: Delivered issue closing keyword is dropped
`devops pr describe` SHALL drop a closing keyword clause that names the delivered issue from the proposal `Why` text and keep the remaining text with one `Closes #<issue>` line in the body.

#### Scenario: Why holds a closing clause for the delivered issue
- **WHEN** a test runs `devops pr describe 5434 --summary "set the pod overhead of RuntimeClass gvisor"` on a proposal whose `Why` holds `This change sets the overhead and closes #5434.`
- **THEN** the command exits 0, and the body holds `This change sets the overhead.` and one `Closes #5434`

## MODIFIED Requirements

### Requirement: devops pr describe refuses and prints nothing
`devops pr describe` SHALL exit 1, print every problem to stderr, and print nothing to stdout when: the summary breaks a rule of the title; the scope of the issue has no label; the text above `Closes` has more than 1,000 characters; the proposal has no section `Why`; the text of the proposal holds a closing keyword for an issue other than the delivered issue; the issue has no change folder, or more than one; or the number is no item of the roadmap. It SHALL NOT cut a text.

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
- **WHEN** the section `Why` says `This closes #7` for issue 1
- **THEN** the exit status is 1 and stderr names the closing keyword

#### Scenario: No change folder
- **WHEN** the issue has no folder under `openspec/changes/` and none in the archive
- **THEN** the exit status is 1 and stderr names the issue

#### Scenario: Not an item
- **WHEN** the number is no item of the roadmap
- **THEN** the exit status is 1 and stderr says that the issue is no item
