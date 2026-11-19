# Design

## Decisions
- Every `gh` and `pr` command sends at least one GitHub request, and a write command reads before it writes, so each row gets the GitHub MCP bound.
- The bound is 300.0, the MCP read bound, which leaves a 240 s margin above the 60 s session read bound.
- The bound has the name `CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS` in `constants.py`, because `defaults.py` imports `constants.py` and the import cannot go the other way.

## Rejected alternatives
- Only the `read_only` rows: the flag says a tool writes nothing, not that it reads nothing, so a write tool would keep the risk.
- A 120 s or 90 s bound: the margin is smaller than the evidence supports, and both are below the MCP read bound.
- Import `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` into `constants.py`: the import is circular.
- Leave the bare numbers in the table: the issue reports the unnamed bound, and a literal leaves it in place.
