## ADDED Requirements

### Requirement: The shadow mark holds a probability from 0 to 1
`ShadowObservation.from_mark` SHALL raise `ValidationError` for a mark whose probability is above 1 or below 0. The report SHALL count such a mark as unreadable and SHALL go on with the other marks. A probability of 1.0 SHALL stay valid and SHALL fall in the last band.

#### Scenario: A mark above 1 or below 0
- **WHEN** a mark holds the probability 1.5 or -0.1 and another issue holds a valid mark
- **THEN** the report counts one unreadable mark and reads the valid mark

#### Scenario: A probability of 1
- **WHEN** a valid mark holds the probability 1.0
- **THEN** the report counts it in the last band
