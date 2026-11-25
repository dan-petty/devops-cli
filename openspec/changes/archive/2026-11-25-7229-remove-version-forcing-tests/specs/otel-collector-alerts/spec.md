## MODIFIED Requirements

### Requirement: The collector rules read only the series the collector serves
Each series that an `otel-collector` rule selects SHALL be a family that the collector serves about itself: a family that the collector prints, or one that it prints from its first event.

#### Scenario: The rules and the capture
- **WHEN** the selectors of the `otel-collector` rules are read
- **THEN** they name five series, and each one is a family that the collector serves
