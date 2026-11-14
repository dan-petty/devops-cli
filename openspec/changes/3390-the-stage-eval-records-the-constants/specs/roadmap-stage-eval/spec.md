## ADDED Requirements

### Requirement: The golden set holds a case whose plan states a wrong constant
The golden set SHALL hold a case that records `SUMMARY_MAX_CHARS` with the value 60 at its base commit and whose plan states that the constant is 40, with one defect of type `other` at the gate `paths` and the message that the constants check gives.

#### Scenario: The replay catches the wrong constant
- **WHEN** The replay runs the case whose plan states `SUMMARY_MAX_CHARS` is 40 and whose recorded value is 60.
- **THEN** The paths gate gives the problem `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40.` and the replay marks the defect `caught`.

#### Scenario: The loader reads the recorded value
- **WHEN** The loader reads the new case.
- **THEN** The facts of the case hold `SUMMARY_MAX_CHARS` with the value 60, and a case that records no constant holds an empty tuple.

### Requirement: The recorder writes the constants of a case
`devops roadmap eval stage --record` SHALL write the name and the staged value of each constant that a case's plan cites into the facts file of that case, and SHALL keep every other recorded fact of the case.

#### Scenario: The recorder records the constant of a case
- **WHEN** The command runs with `--record` on a case whose plan states `SUMMARY_MAX_CHARS` and whose base commit defines it as 60.
- **THEN** The facts file of the case holds `SUMMARY_MAX_CHARS` with 60, and every other fact is unchanged.

#### Scenario: The recorder writes no constant for a plan that cites none
- **WHEN** The command runs with `--record` on a case whose plan cites no constant.
- **THEN** The facts file of the case holds an empty constants list.
