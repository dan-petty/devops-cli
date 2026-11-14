# Design

## Context

`_Judge.judge` in `implement.py` checks the status, the claim, the route, the author and the plan gates. `StageJob._dependency` in `stage.py` reads the Dependencies section of the body, with `body_dependencies` and `title_dependencies`, and names each open issue.

## Goals

- Read one set of dependency declarations in both jobs.
- Leave the stage reason unchanged.

## Decisions

- **A shared `open_dependency`.** The helper takes the item, the store and the items, and returns the message or None.
- **The plan dependencies come from the proposal.** `_plan_reason` already reads the proposal for the branch or the default branch, so it calls `open_issue_dependencies` on `issue_dependencies(proposal.dependencies)` before the plan gates.
- **The body check runs before the route.** An item with an open dependency needs no branch read and no pull request read.

## Risks

- A plan whose dependency entry is not `#N: reason` gives no number, as `issue_dependencies` documents. The plan check reports the form separately.

## Tests

- A body dependency on an open item leaves the item out with the dependency reason.
- A plan dependency on an open item leaves the item out with the reason.
- Closed dependencies allow selection.
- The stage selection tests stay green.
