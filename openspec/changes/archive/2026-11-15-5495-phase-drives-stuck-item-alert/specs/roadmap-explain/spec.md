# roadmap-explain Specification

## ADDED Requirements

### Requirement: Explain prints item phase and phase age
`devops roadmap explain <issue>` SHALL print the phase and the phase age of the issue.

#### Scenario: Explain prints the phase and phase age of an item
- **WHEN** `devops roadmap explain 7` runs on an open item
- **THEN** the output includes the phase of the item and its phase age
