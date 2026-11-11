# Design

## Decisions

- The four `resource://gh/` resources take `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` (300 s), five times the session read bound of 60 s. A listing reads one page for each read, so the bound around it holds more than one read, and the margin lets the read fail first.
- The bound is a rule for the namespace: each resource under `resource://gh/` takes it. `resource://gh/project/status` reads only the local project template. The longer bound costs it nothing, and a later read of GitHub in it needs no new decision.
- The chain test keeps its rule (each bound is shorter than the next one) and holds more than one chain. A chain is the bounds around one GitHub read, the innermost first. The chain of the implement job and the chain of a `resource://gh/` resource share the Valkey bound and the session read bound. The test runs each pair once.
- The test of the resources lists the resources of the server under `resource://gh/`, reads each one through the `mcp_dispatcher` fake, and compares the bound of each dispatch with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`. The test names the four URIs, so a new `resource://gh/` resource fails it until the test names that resource and its bound.

## Rejected alternatives

- A session read bound shorter than 30 s, for example 20 s: rejected. It changes every GitHub read, and the issue names it as the larger change.
- `DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS` (60 s) for the resources: rejected. It is equal to the read bound, so the dispatch and the read can stop at the same time, and the owner rule asks for a margin.
- A new constant for the bound of the `resource://gh/` resources: rejected. `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` exists and holds the bound, and a second name for the same 300 s is one more number to keep.
- One chain with the MCP bound between the session read and the watch of the checks: rejected. An MCP read does not hold the watch of the checks, so the pair "MCP bound < watch" is not a rule of the code.
- The MCP tools of `CONST_MCP_EXPOSURE_TABLE` that read GitHub in 60 s or less: out of scope. The issue names the resources. #4784 holds the tools.
