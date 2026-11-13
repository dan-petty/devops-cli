## ADDED Requirements

### Requirement: The verify report states the ceiling of the findings that return a good plan
The report SHALL state the ceiling `CONST_ROADMAP_VERIFY_GOOD_RETURNING_CEILING`, after the floor, and whether the mean of the findings that would return a good plan, for each good plan that the run verified, passes it. A finding returns a plan only when it is open, so only a blocker or a major finding counts. A run that verified no good plan SHALL state that the ceiling is not scored. The JSON report SHALL hold the mean as `good_returning_mean`. The ceiling SHALL NOT change the exit code.

#### Scenario: A mean above the ceiling
- **WHEN** the run verifies two good plans, and each gets more findings that return it than the ceiling
- **THEN** the report states the ceiling and says that the mean is above it

#### Scenario: A mean within the ceiling
- **WHEN** the run verifies two good plans, and no finding returns either of them
- **THEN** the report states the ceiling and the mean of 0.00, and says that the mean does not pass it

#### Scenario: No good plan
- **WHEN** the run verifies no good plan
- **THEN** the report says that the ceiling is not scored
