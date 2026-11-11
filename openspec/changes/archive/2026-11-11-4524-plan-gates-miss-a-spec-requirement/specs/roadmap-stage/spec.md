## ADDED Requirements

### Requirement: Refuse a requirement text over the OpenSpec limit
`check_proposal` SHALL refuse each ADDED and MODIFIED requirement of a spec delta whose text is longer than `REQUIREMENT_MAX_CHARS`, the 500 characters that the strict OpenSpec validation of a spec allows. It SHALL count UTF-16 code units, as OpenSpec does. The problem SHALL name the requirement, its length and the limit, and `devops roadmap plan-check` SHALL report it with the rule `stage`.

#### Scenario: An ADDED requirement of 543 characters
- **WHEN** a spec delta ADDs a requirement whose text has 543 characters
- **THEN** `check_proposal` returns one problem that names the requirement, the length 543 and the limit 500

#### Scenario: The MODIFIED requirement of the #3462 plan
- **WHEN** a spec delta modifies a requirement with the text of 543 characters of the #3462 plan
- **THEN** `check_proposal` returns one problem that names the requirement and the length 543

#### Scenario: A requirement at the limit
- **WHEN** a spec delta holds a requirement text of exactly 500 characters
- **THEN** `check_proposal` returns no problem

#### Scenario: A character outside the Basic Multilingual Plane
- **WHEN** a requirement text holds 499 other characters and one emoji
- **THEN** `check_proposal` returns a problem with the length 501

#### Scenario: plan-check on a long requirement
- **WHEN** `devops roadmap plan-check` reads a change folder with a requirement text of 543 characters
- **THEN** the result holds one problem with the rule `stage` that names the requirement and the length 543
