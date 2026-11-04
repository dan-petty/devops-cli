## ADDED Requirements

### Requirement: A title whose summary is over the limit is refused
The stage job SHALL refuse an item whose issue title has a Conventional Commit type and a summary longer than `SUMMARY_MAX_CHARS` UTF-16 code units, counted by `summary_length`.

#### Scenario: A summary of 61 UTF-16 units is refused
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 61 UTF-16 code units
- **THEN** The stage job leaves the item out, and its reason names the current length and the limit of 60

#### Scenario: A summary of 60 UTF-16 units passes the length check
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 60 UTF-16 code units
- **THEN** The stage job does not refuse the item for the length of its summary

#### Scenario: A title with no type keeps its reason
- **WHEN** A Ready item has a title with no Conventional Commit type and a summary longer than the limit
- **THEN** The stage job leaves the item out and its reason names the missing type, not the length of the summary
