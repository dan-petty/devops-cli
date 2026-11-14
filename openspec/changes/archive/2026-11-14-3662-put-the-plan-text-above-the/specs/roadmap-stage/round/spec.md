## ADDED Requirements

### Requirement: A plan body puts its text above the Plans line
`plan_body_problems` SHALL read the plan text above the `Plans #<issue>` line, as the delivery form reads its text above `Closes`. A plan body with too little text SHALL be refused with a message that names `Plans`, states that the text goes above it, and gives the minimum of 20 characters. A delivery body SHALL keep the message that names `Closes`. `build_plan_body` SHALL write the text, then `Plans`, then `Change:`.

#### Scenario: Text above Plans
- **WHEN** a plan body holds the text, then `Plans #<issue>`, then the `Change:` line of the active folder of the same issue
- **THEN** `plan_body_problems` returns an empty list

#### Scenario: A short plan text
- **WHEN** a plan body holds fewer than 20 characters above `Plans`
- **THEN** the message names `Plans`, says that the text goes above it, and gives the minimum of 20 characters

#### Scenario: A short delivery text
- **WHEN** a delivery body holds fewer than 20 characters above `Closes`
- **THEN** the message names `Closes` and holds no `Plans`
