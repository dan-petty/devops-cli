## ADDED Requirements

### Requirement: The Planned limit does not stop a refine round
The setting `roadmap.stage.planned_limit` SHALL NOT stop a refine round from taking a New item and setting its Status to Ready. A round SHALL select the same items with the limit at 1 and 50 Planned items as it does with no Planned items.

#### Scenario: The limit is 1 with 50 Planned items
- **WHEN** `roadmap.stage.planned_limit` is 1, 50 open items are Planned, and one New item is in the backlog
- **THEN** the round selects the New item, makes one model call for it, and sets its Status to Ready
