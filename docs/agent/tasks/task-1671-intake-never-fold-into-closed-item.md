# Task: Intake Never Folds Candidate into Closed Completed Item (#1671)

**Issue**: [#1671](https://github.com/dan-petty/devops-cli/issues/1671)
**Scope**: scope/roadmap
**Feasibility**: Verified against intake triage duplicate check, IssueRecord state models, and in-memory store tests.

## Description
When `devops roadmap intake` compared candidates against existing items on the board, completed/Done items were included in the comparison set. If the model proposed a Done item as `duplicate_of`, intake treated the candidate as a duplicate and folded it into the closed item, resulting in nothing being filed and lost defect reports for regressions in shipped work.

This change ensures that:
- Closed completed/Done items on the board are never fold targets.
- When a candidate matches a closed completed item, it is not treated as a duplicate; instead, it is placed and filed as a new issue on the board.
- The new issue's body references the original completed item (e.g. `regression of #1135, shipped in v0.2.35`).
- Open items and issues closed as not planned remain valid duplicate/fold targets as before.

## Acceptance Criteria
- [x] **Done item matches are filed**: A candidate matching only a closed completed (Done) item is placed and filed as a new issue with a regression reference in its body.
- [x] **Open item duplicates fold**: A candidate matching an open item folds into that item as duplicate.
- [x] **Not-planned item duplicates fold**: A candidate matching an item closed as not planned folds into that decision as duplicate.
