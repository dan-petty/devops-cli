## ADDED Requirements

### Requirement: The inbox states when the Planned limit holds
`devops roadmap inbox` SHALL list one line when the count of open Planned items is at the setting `roadmap.stage.planned_limit` or over it. The line SHALL name the count and the setting, SHALL show `-` as its number and its age, and SHALL give a way to clear it: deliver Planned items, or raise the setting. The line SHALL come after the line of the labels. Under the limit, the inbox SHALL list no such line.

#### Scenario: At the limit
- **WHEN** 2 open items are Planned, 1 closed item is Planned, and the setting is 2
- **THEN** the output lists one line that names the count 2 and `roadmap.stage.planned_limit`, with `-` as its number and age

#### Scenario: Under the limit
- **WHEN** 1 open item is Planned and the setting is 2
- **THEN** the output lists no such line
