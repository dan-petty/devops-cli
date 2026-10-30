## ADDED Requirements

### Requirement: qdrant-retry-wait-uses-clock-seam
The Qdrant retry SHALL wait between attempts through the sleep parameter of tenacity, supplied by the clock seam, and SHALL NOT call time.sleep directly.

#### Scenario: retry records waits on the clock fixture
- **WHEN** a Qdrant operation fails and the retry runs on the clock fixture
- **THEN** the clock fixture records the wait durations and no real wall-clock time is spent

#### Scenario: retry backoff sequence is recorded in order
- **WHEN** three retry attempts occur with the default backoff of 0.5 times the attempt number
- **THEN** the clock fixture records waits of 0.5, 1.0, and 1.5 seconds in that order
