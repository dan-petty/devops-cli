## ADDED Requirements

### Requirement: loki-url-config-key
The config system SHALL recognize loki.url as a valid key for setting the Loki service address.

#### Scenario: set-loki-url-succeeds
- **WHEN** A user runs devops config set loki.url http://example.com:3100
- **THEN** The command exits with code 0 and does not print Unknown config key
