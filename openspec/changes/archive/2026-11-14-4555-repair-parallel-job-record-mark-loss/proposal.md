# Proposal: #4555

## Why
A job record write joins the record that the issue holds at its read (`GET`). GitHub provides no conditional write for an issue. When two writers read an issue before either writes (`PATCH`), the second write overwrites the marks of the first writer. The lost marks raise no error. This causes data loss between parallel roadmap jobs.

Closes #4555.

## What Changes
- Add a read-back check after each record `PATCH` in `GitHubRoadmapStore`.
- When a mark that this writer set is missing after the `PATCH`, rewrite the record with the missing mark, up to 2 times.
- Raise `RoadmapRecordMarkLostError` when a third miss occurs.
- Add telemetry counters `devops_cli_roadmap_record_repairs_total` and `devops_cli_roadmap_record_lost_edit_total`.
- Log each repair and increment the repair counter.
- Detect a person's edit to the text outside the record block between the read and the `PATCH`, restore that text, and increment the lost-edit counter.

## Capabilities
- `roadmap-record-repair`: Read-back verification and automatic repair of job record marks and text after an issue update.

## Impact
- Parallel writes to an issue by different processes or lanes retain all written marks.
- Repaired record writes and restored human edits emit telemetry metrics.
- Failures after two repair attempts raise a clear error identifying the item and the missing mark.

## Feasibility
The GitHub REST API returns the updated issue on `PATCH`, and a subsequent `GET` reads the latest state. The GitHub fake supports interleaved reads and writes for deterministic testing.

## Existing Tool Considered
No open tool provides conditional writes or fencing for GitHub issue bodies. Written cost: about 90,000 tokens and 4 hours to build, about 5,000 tokens a month to keep, and about 10,000 tokens to fix.
