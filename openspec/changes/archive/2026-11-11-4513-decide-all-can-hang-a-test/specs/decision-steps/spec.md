## ADDED Requirements

### Requirement: Decision requests use one event loop and a time limit
`decide_all` SHALL send all requests of one call on one event loop in the calling thread, so that a model that the requests share stays on the loop of its lock and client. It SHALL raise `TimeoutError` when a request does not end within `timeout` seconds, so that the step fails open and no caller waits for good.

#### Scenario: A shared model serves every request on one loop
- **WHEN** `decide_all` sends three requests with one model over a fake Jev endpoint
- **THEN** the endpoint records the same event loop for the three requests

#### Scenario: A request that is never answered
- **WHEN** the fake Jev endpoint holds a request open and `decide_all` runs with a timeout of 0.01 seconds
- **THEN** `decide_all` raises `TimeoutError`
