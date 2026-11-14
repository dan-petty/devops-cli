# Design

## Context

`RoadmapMcpToolset.__aenter__` calls `MCPToolset.__aenter__` once and wraps any exception in `RoadmapMcpUnavailableError`.

## Goals

- Survive the policy start delay of a new pod.
- Do not delay an authentication failure.

## Decisions

- **tenacity `AsyncRetrying`.** A predicate retries a `ConnectionRefusedError`, an `OSError` and an exception whose class name holds `connect`, which covers `httpx.ConnectError` without an import.
- **A bounded budget from constants.** `stop_after_delay` reads `ROADMAP_MCP_CONNECT_RETRY_SECONDS`; the wait reads the initial and maximum constants.
- **The existing error at the end.** After the budget, the last connection error is the cause of `RoadmapMcpUnavailableError`, so the message keeps the reason.

## Risks

- A name test for `connect` could retry an unrelated class. The name is specific to a connection error, and the budget bounds the cost.

## Tests

- A refused attempt twice then a success enters once.
- Every attempt refused raises the error with the URL and the last cause.
- An authentication failure is attempted once.
- The constants hold the budget values.
