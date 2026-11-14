## ADDED Requirements

### Requirement: The stage context holds the text of a cited requirement
The stage context SHALL hold the name and the text of each base requirement that a cited capability, requirement name, path, command or symbol of the issue matches.

#### Scenario: A plan cites a command that a requirement names
- **WHEN** A plan cites a command that the text of one requirement of a fake spec names.
- **THEN** The stage context holds the name and the text of that requirement, and the test asserts both.

### Requirement: The stage context bounds the requirement text
The stage context SHALL cut the matching requirements at a named constant of 12 requirements and then at a named constant of 6000 characters, and each constant SHALL carry a docstring.

#### Scenario: A spec with more matches than the count bound
- **WHEN** A fake spec holds more matching requirements than the count constant allows.
- **THEN** The stage context holds exactly the count constant's number of requirements, and the test asserts the count.

#### Scenario: A match longer than the character bound
- **WHEN** The text of the matching requirements is longer than the character constant allows.
- **THEN** The requirement text of the stage context is at most the character constant's length, and the test asserts the length.

### Requirement: The stage context orders the requirement text by relevance
The stage context SHALL place a requirement whose capability or name the issue cites before a requirement whose text only a cited path, command or symbol matches.

#### Scenario: A name match outranks a text match
- **WHEN** A plan cites a requirement name and a command that the text of another requirement holds.
- **THEN** The requirement with the name match comes before the requirement with the text match, and the test asserts the order.
