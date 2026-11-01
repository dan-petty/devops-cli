## ADDED Requirements

### Requirement: unique-thinking-removed
The ThinkingStreamProcessor SHALL not expose a unique_thinking property.

#### Scenario: property is absent
- **WHEN** a ThinkingStreamProcessor instance is created
- **THEN** the instance has no unique_thinking attribute
