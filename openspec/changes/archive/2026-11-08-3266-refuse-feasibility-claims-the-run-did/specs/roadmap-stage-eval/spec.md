## ADDED Requirements

### Requirement: The golden set holds a plan whose read claim its trace does not support
The golden set SHALL hold a replay case from #3205 or #3237 whose facts give a trace of zero calls, and the replay SHALL refuse its unsupported read claim.

#### Scenario: The replay refuses the case
- **WHEN** `devops roadmap eval stage --replay` runs on the golden set.
- **THEN** The case is present, and the `paths` gate refuses its unsupported read claim.
