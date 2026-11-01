## ADDED Requirements

### Requirement: test-worker-import-preload
The test session SHALL import the heavy modules pydantic_ai, anthropic, kubernetes, and textual once per xdist worker via a session-scoped fixture, so that no test body carries the first-import cost of a heavy module.

#### Scenario: heavy modules present after session start
- **WHEN** the session-scoped fixture completes on a worker
- **THEN** sys.modules contains pydantic_ai, anthropic, kubernetes, and textual before the first test executes

#### Scenario: fixture scope is session
- **WHEN** the fixture definition is inspected
- **THEN** the scope parameter of the pytest.fixture decorator is 'session'
