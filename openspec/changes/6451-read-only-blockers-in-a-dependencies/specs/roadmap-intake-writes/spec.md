## ADDED Requirements

### Requirement: The filed body names its source under its own heading
Intake SHALL file the source of a candidate under a `## Source` heading after the body of the candidate. It SHALL write no source line inside the Dependencies section, so that the source names no dependency.

#### Scenario: A filed candidate with a source
- **WHEN** `NewCandidate.filed_body` builds the body of a candidate whose body ends with `## Dependencies` and whose source is `#4989`
- **THEN** the body holds a `## Source` heading before `#4989`, and `body_dependencies` of that body returns an empty list
