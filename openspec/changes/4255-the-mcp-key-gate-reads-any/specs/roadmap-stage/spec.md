## MODIFIED Requirements

### Requirement: Resolve cited MCP exposure keys
The plan check SHALL resolve each quoted tuple key that a plan cites against `CONST_MCP_EXPOSURE_TABLE`. It SHALL read a quoted tuple as a cited key only when the sentence that holds the tuple names `CONST_MCP_EXPOSURE_TABLE` or the words "exposure table".

#### Scenario: Unknown MCP exposure key is refused
- **WHEN** A plan cites the exposure table key `("ai", "ast-graph")`.
- **THEN** The check returns a problem that names `("ai", "ast-graph")` and refuses the plan.

#### Scenario: Known MCP exposure key is accepted
- **WHEN** A plan cites the exposure table key `("ai", "ast", "graph")`.
- **THEN** The check returns no MCP exposure problem for that key.

#### Scenario: A quoted tuple of another table is no key
- **WHEN** A plan says that the fixture table of `tests/conftest.py` lists `("reset_logfire_bridge",)`.
- **THEN** The check returns no MCP exposure problem.

#### Scenario: The sentence of the tuple decides
- **WHEN** A plan names the exposure table in one sentence and quotes the tuple `("ai", "ast-graph")` in the next sentence.
- **THEN** The check returns no MCP exposure problem.
