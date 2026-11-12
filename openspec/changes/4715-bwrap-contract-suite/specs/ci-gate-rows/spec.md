## ADDED Requirements

### Requirement: The bwrap row runs the sandbox contract suites where the host can make a sandbox
The table of `devops ci` SHALL hold a row `bwrap` that runs `pytest -m bwrap -n 0` with a bound for each test over the two contract suites of the sandbox, after the host check of the sandbox executor. On a host that fails the check, the row SHALL start no test, SHALL pass, and SHALL show `skipped: <cause>`, also in a cached verdict.

#### Scenario: A host that can make the sandbox
- **WHEN** `devops ci --only bwrap` runs and bubblewrap makes a sandbox on the host
- **THEN** the row starts `uv run pytest -m bwrap -n 0 --timeout=60` with `tests/sandbox/test_host_sandbox.py` and `tests/ai/test_tool_executor_contract.py`

#### Scenario: A host that cannot make the sandbox
- **WHEN** `devops ci --only bwrap` runs and bubblewrap exits 1 with `bwrap: setting up uid map: Permission denied`
- **THEN** the row starts no test, the gate exits 0, and the output shows `[bwrap] skipped: bubblewrap cannot make a sandbox on this host: bwrap: setting up uid map: Permission denied`

#### Scenario: A cached verdict keeps the skip
- **WHEN** a full gate passed with the row skipped, and the gate runs again on the same tree
- **THEN** the cached summary shows the row as skipped and starts no command
