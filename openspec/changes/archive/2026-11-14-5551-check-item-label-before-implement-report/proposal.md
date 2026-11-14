# Proposal: #5551

## Why
The implement row reads the name of a runner Job from the record block of an issue (`implement.job`). An outside author can write the name of an ended runner Job of another item into their own issue. The round then posts the log tail of that Job on the issue of the outside author, and records state on it. This causes disclosure of the log tail. Closes #5551.

## What Changes
Check the item label of a runner Job before `_report_ended` reports it. If the item label of the Job does not match the number of the item that records it, skip the item and write nothing. Keep the current report for a Job that is gone from the cluster.

## Capabilities
- Prevent log disclosure by verifying that the runner Job label matches the issue number before report.
- Maintain existing reporting behavior for legitimate runner Jobs and gone Jobs.

## Impact
- Protects item logs from unauthorized disclosure when an author edits issue text.
- No change to existing cluster resources or metrics.

## Feasibility
The Kubernetes runner Job already carries the item label `roadmap.devops-cli/item` added in #4558. The stage row implements the same label guard in #4559 (`src/devops_cli/roadmap/stage/stage_submit.py`).

## Existing Tool Considered
No open tool or library covers this in-repo check. Building this check requires minimal code in `src/devops_cli/roadmap/implement/implement_submit.py`. The written cost is approximately 2,000 tokens to build, 500 tokens to maintain, and 0.5 day elapsed.
