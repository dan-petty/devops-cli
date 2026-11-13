## MODIFIED Requirements

### Requirement: Decision requests use one event loop and a time limit
`decide_all` SHALL send all requests of one call on the blocking portal that `decide_with_jev` uses, so that a model that the requests share stays on the loop of its lock and client, and it SHALL NOT call `asyncio.run`. `adecide_all` SHALL await the same gathered requests for a caller that runs in an event loop. Both SHALL raise `TimeoutError` when a request does not end within `timeout` seconds, so that the step fails open and no caller waits for good.

#### Scenario: A shared model serves every request on one loop
- **WHEN** `decide_all` sends three requests with one model over a fake Jev endpoint
- **THEN** The endpoint records the same event loop for the three requests

#### Scenario: A request that is never answered
- **WHEN** The fake Jev endpoint holds a request open and `decide_all` runs with a timeout of 0.01 seconds
- **THEN** `decide_all` raises `TimeoutError`

#### Scenario: A call from a thread with a running loop
- **WHEN** `decide_all` and `adecide_all` run inside a coroutine that `asyncio.run` runs, with the fake Jev endpoint
- **THEN** Both return the responses in order and raise no `RuntimeError`
