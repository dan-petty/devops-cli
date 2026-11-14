## ADDED Requirements

### Requirement: First connection retry
`RoadmapMcpToolset.__aenter__` SHALL retry a refused first connection until it succeeds or `ROADMAP_MCP_CONNECT_RETRY_SECONDS` expires, with exponential delays from `ROADMAP_MCP_CONNECT_RETRY_INITIAL_SECONDS` capped at `ROADMAP_MCP_CONNECT_RETRY_MAX_SECONDS`. When the budget expires, it SHALL raise `RoadmapMcpUnavailableError` with the target URL and the last connection error as its cause. It SHALL NOT retry an authentication failure.

#### Scenario: A refused attempt then a success
- **WHEN** the first two attempts raise `ConnectionRefusedError` and the third succeeds
- **THEN** `__aenter__` returns the toolset and no `RoadmapMcpUnavailableError` is raised

#### Scenario: Every attempt is refused
- **WHEN** every attempt within the budget raises `ConnectionRefusedError`
- **THEN** `RoadmapMcpUnavailableError` names the target URL and its cause is the last `ConnectionRefusedError`

#### Scenario: An authentication failure
- **WHEN** the first attempt raises an authentication error
- **THEN** the client makes one attempt and raises `RoadmapMcpUnavailableError`

#### Scenario: The budget comes from constants
- **WHEN** the retry runs
- **THEN** the total budget is `ROADMAP_MCP_CONNECT_RETRY_SECONDS` from `src/devops_cli/config/constants.py`, and the initial and maximum delays are its two companions
