## ADDED Requirements

### Requirement: The golden set holds a case of the open-finding stop
The golden set SHALL hold a case recorded from #3174 whose plan carries a single group titled `placeholder`, and the replay SHALL report that case with its defect.

#### Scenario: The replay runs the recorded case
- **WHEN** The replay runs the case recorded from #3174.
- **THEN** The report lists the case with its placeholder group, and the test asserts the expected result.
