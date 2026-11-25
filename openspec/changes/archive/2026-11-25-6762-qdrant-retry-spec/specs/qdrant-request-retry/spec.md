## ADDED Requirements

### Requirement: qdrant-retry-wait-uses-clock-seam
The Qdrant retry loop SHALL wait between attempts through the `sleep` parameter supplied by the clock seam (`clock_seam.sleep`), and SHALL NOT call `time.sleep` directly.

#### Scenario: retry records waits on the clock fixture
- **WHEN** a Qdrant operation fails and `_execute_with_retry` runs on the clock fixture
- **THEN** the clock fixture records the wait durations and no real wall-clock time is spent

#### Scenario: retry backoff sequence is recorded in order
- **WHEN** `DEFAULT_MAX_RETRIES` (3) attempts run with the default backoff of `0.5 * attempt` between failed attempts
- **THEN** the clock fixture records waits of `0.5` and `1.0` seconds in that order
