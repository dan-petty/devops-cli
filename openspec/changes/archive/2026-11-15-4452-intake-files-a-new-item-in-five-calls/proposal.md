# Proposal: #4452

## Why

`devops roadmap intake --confirm` filed a new candidate with 13 GitHub calls one after another,
and two profiled runs took about 30 s (#4404). The reads of `set_field` and the separate label
calls protect nothing for an issue that no other writer has seen. Closes #4452.

## What Changes

- A new candidate goes in one `create_issue` request that carries every label and the job record
  of Status, Value and Effort, and intake sends no `label_issue` and no field write for it.
- An existing candidate writes Status, Value and Effort in one `RoadmapStore.set_fields`
  request after one read, which refuses a field that a person changed.
- The Priority keeps its own `set_field`, last. The dry-run plan lists the new steps.

## Capabilities

`roadmap-intake-writes`, a new capability: six requirements for the writes of a new candidate,
the batched write and the dry run.

## Impact

The write phase of a new candidate falls from 13 calls to 6. The store gains `set_fields`; the
in-memory store and the contract suite implement and check it. No manifest, image or command
option changes.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): `_apply_placement` made the 13
calls, `GitHubRoadmapStore.set_field` reads before each `PATCH`, and `create_issue_args` already
takes labels. The intake and store suites pass, and the request-count test pins 6.

## Existing Tool Considered

The GitHub REST API takes every label in the create request and every label family in one issue
`PATCH`. Nitro, a UI or a second library adds no call count. No new tool.
