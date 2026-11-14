# Design

## Context

`_return_plan_defects` builds the comment from the refused problems and the failure reason. It adds the reason only when `failure.stopped_by_checks` is false.

## Goals

- One bullet for the degenerate reply.
- Keep the reason path for a stop that the checks did not refuse.

## Decisions

- **The flag on the stop.** The degenerate reply is a refused reply, and its problem is the reason.
- **No spec delta.** The existing requirement already states this case.

## Risks

- None beyond the flag.

## Tests

- A round with a degenerate reply at the limit returns the item to New with one bullet.
