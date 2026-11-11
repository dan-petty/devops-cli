# Design

## Decisions

- The read bound is a constant in `config/defaults.py`, as the connect bound of the session is (`DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS`). `session_client` passes it to `request_timeout(read=...)`. The entry point's default read bound does not change, so every other client keeps it.
- 60 s is six times the 10 s after which GitHub ends a REST request. A slow network or a large page still gets its answer, because the bound is for each chunk of data, not for the full body.
- The chain test lists the bounds around a GitHub read by name, innermost first: `DEFAULT_VALKEY_TIMEOUT_SECONDS` (the cache tier in front of a read), `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`, and `DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS` (the watch of the checks, which reads through the session at each poll). A name that is not defined counts as an endless bound, so the test fails, and does not error, when a bound is missing.
- The reference step (120 s) and the alternatives unit deadline of #4573 (3,600 s) are not in the code yet. Each one joins the chain in the item that adds it.
- The test of a silent host uses httpx2's own transport against a loopback listener that accepts no connection, behind the transport hook. The kernel completes the connect, so only the read bound ends the wait. The test shortens the bound to 0.05 s and does not measure the time.

## Rejected alternatives

- A setting in `config.yaml` for the read bound: rejected. GitHub's own 10 s limit does not change for each user, and the connect bound is a constant too.
- A lower default read bound for every client of the entry point: rejected. Downloads of release archives and model replies need long reads (`DEFAULT_HTTP_TIMEOUT_SECONDS`, "API requests & downloads"), and the item asks to keep them.
- The MCP tool call (30 s) in the chain: rejected. The design of the project brain lists it between the GitHub read and the reference step, and the issue leaves it out of the chain. This was wrong: `resource://gh/issues/status` holds a GitHub session read, and its bound of 30 s was shorter than the read. #4678 gives the `resource://gh/` resources `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` (300 s) and adds their chain to the test.
- A bound on the write of the session: out of scope. The item names the read, and `request_timeout` sets the write bound for every client of the entry point.
- A test that shows the read through `WebFake.time_out` only: rejected. The fake raises `ReadTimeout` at once and does not show that the client's bound reaches the socket.
