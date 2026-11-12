## MODIFIED Requirements

### Requirement: A placeholder text is one rule
`is_placeholder` SHALL be true for the texts `x`, `y`, `probe`, `placeholder`, `none`, `ignore`, `pending`, `draft`, `temporary` and "Placeholder not final.", for `__PROBE__`, and for a text that starts with "Not yet:", with no case and no punctuation around the text. `ReplyText` SHALL apply that rule as a validator and SHALL raise the error type `placeholder_text`.

#### Scenario: The filler words
- **WHEN** `is_placeholder` reads `x`, `y`, `probe`, `__PROBE__`, `placeholder` and `none`
- **THEN** it is true for each

#### Scenario: The stub texts of the census
- **WHEN** `is_placeholder` reads `ignore`, `Pending`, `draft`, `temporary` and "Placeholder not final."
- **THEN** it is true for each

#### Scenario: The refusal of a task
- **WHEN** `is_placeholder` reads "Not yet: I need to inspect the repository first."
- **THEN** it is true

#### Scenario: A real text
- **WHEN** `is_placeholder` reads "The probe shows the path", "x-ray the cache" and "Draft the release notes"
- **THEN** it is false for each
