## ADDED Requirements

### Requirement: The ladder names only the step classes that a step reads
The step classes SHALL be `edit`, which is a group of a change, and `repair`, which is the fix of a failed check. The setting `roadmap.implement.ladder` SHALL hold a tier list for each of these two classes by default, and SHALL refuse a key that is not one of them, with a message that names the key and the classes.

#### Scenario: The default ladder
- **WHEN** the settings are read with no ladder set
- **THEN** the ladder holds the keys `edit` and `repair`, and no other key

#### Scenario: A removed class is named
- **WHEN** the ladder names the key `plan` or `review`
- **THEN** the settings are refused with a message that the ladder names no step class with that key
