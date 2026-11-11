## ADDED Requirements

### Requirement: The trace option prints the argument digest of a tool call
`explain <issue> --trace` SHALL show in the line of a `tool` event the digest of its argument, when the event holds one, so that a reader sees a repeated call. A `tool` event with no digest SHALL show no argument part.

#### Scenario: The same call twice
- **WHEN** the trace holds two `tool` events with the digest `abc123abc123`
- **THEN** each line says `[argument abc123abc123]`

#### Scenario: A tool call with no digest
- **WHEN** a `tool` event holds no digest
- **THEN** its line has no argument part
