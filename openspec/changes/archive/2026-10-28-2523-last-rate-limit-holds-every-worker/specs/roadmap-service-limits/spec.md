# Spec Delta

## MODIFIED Requirements

### Requirement: A rate limit holds every worker
When a GitHub request of one worker meets a rate limit, no worker SHALL send a GitHub request of the identity before the wait that the rate limit asks for ends, also when the request is not sent again because its retries are spent.

#### Scenario: A secondary limit with retry-after
- **WHEN** one worker's request gets a 403 with `retry-after: 60` and another worker then sends a request
- **THEN** the first worker waits 60 s before its retry, and the other worker's request waits until those 60 s end

#### Scenario: The last rate limit of a request
- **WHEN** one worker's request meets a secondary limit at each attempt, through the session with `retry-after: 60` or through gh, its round fails when its retries are spent, and another worker then sends a request
- **THEN** the other worker's request waits at least 60 s after the last refusal
