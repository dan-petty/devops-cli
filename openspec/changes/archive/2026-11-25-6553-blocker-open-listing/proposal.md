# Proposal: #6553

## Why
Refine reads the state of each recorded blocker with one GitHub request through `store.item`. Each round already holds the open listing from `store.open_items()`. The 202 blocked items make 331 to 391 recorded-blocker reads in each refine round. Reusing the open listing eliminates all `store.item` requests for recorded blockers.

## What Changes
- Refine uses the open item numbers from the open listing to determine whether recorded blockers are open, making no `store.item` requests.
- `open_issue_dependencies` takes the open item numbers as a required parameter and makes no `store.item` requests.
- Recorded blockers that are open issues but lack priority labels (not present in the open listing) evaluate to no blocker.

## Capabilities
- `roadmap-dependency-cycle`: Add requirements for reading blocker and dependency state from the open listing without calling `store.item`.

## Impact
- Eliminates 300+ uncached `gh api` subprocess calls per refine round.
- Reduces refine round latency and avoids GitHub API rate limit consumption.

## Feasibility
- Verified in `src/devops_cli/roadmap/refine/refine.py` and `src/devops_cli/roadmap/dependencies.py`. Callers already hold `open_items` from `store.open_items()`.

## Existing Tool Considered
No open tool or library covers this internal data-flow optimization. The change reuses `GitHubRoadmapStore.open_items()` which each round already holds.
