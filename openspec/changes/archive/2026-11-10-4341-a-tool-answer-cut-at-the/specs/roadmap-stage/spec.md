## ADDED Requirements

### Requirement: A cut tool answer says so
The answer of a read-only tool of a roadmap job SHALL end at a whole line when the character limit shortens it, and a single line over the limit SHALL be cut. An answer that lost text to the line limit or to the character limit SHALL end with the line `(more lines are left out)`. An answer under both limits SHALL have no notice.

#### Scenario: The character limit drops lines
- **WHEN** a tool answers with 100 lines of 100 characters and the character limit is 8,000
- **THEN** the answer holds whole lines only, and its last line is `(more lines are left out)`

#### Scenario: An answer under both limits
- **WHEN** a tool answers with 10 lines of 100 characters
- **THEN** the answer is those lines and has no notice

#### Scenario: One line over the limit
- **WHEN** a tool answers with one line of 8,500 characters
- **THEN** the answer is the first 8,000 characters of the line and the notice
