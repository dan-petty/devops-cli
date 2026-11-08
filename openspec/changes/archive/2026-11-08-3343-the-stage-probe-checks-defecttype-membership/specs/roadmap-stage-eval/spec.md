## ADDED Requirements

### Requirement: The golden set holds the incident plan
The golden set SHALL hold the plan of pull request #3305 as a case whose `issue` is 3264.

#### Scenario: The incident case loads
- **WHEN** `load_cases` reads `tests/fixtures/roadmap_eval/stage` at the commit that holds the case
- **THEN** the cases hold a case whose `issue` is 3264 and whose `pull` is 3305

#### Scenario: The note names the claim
- **WHEN** the case of pull request #3305 is read
- **THEN** one note of the case holds the text `kind: placeholder`

#### Scenario: The incident case passes every gate
- **WHEN** `replay_all` runs on the case of pull request #3305
- **THEN** `report.failures` is an empty list
