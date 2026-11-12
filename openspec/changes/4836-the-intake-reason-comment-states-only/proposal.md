# Proposal: #4836

## Why

The intake reason comment states again the type, scope, Priority, Value and Effort that the labels of the item already show, and a header line that is the same on each item. A reader must read about 870 characters to find the one or two facts that the labels do not show. Closes #4836.

## What Changes

- The reason comment holds only the facts that the labels do not show: a scope that `.github/labels.yml` does not declare, the reason of a Priority other than P2-Medium, the reason of a P0 decision on evidence, the possible original and the related item.
- The comment has no header line. The milestone of an item is on the issue, so the comment does not name it.
- When no such fact exists, intake posts no reason comment and reads no comments of the issue.
- The checked proposal of intake drops the type, Value and Effort reasons of the model, which no reader uses now. The reply schema of the model does not change.
- `docs/roadmap/intake.md` tells what the comment holds.

## Capabilities

- `roadmap-intake-reason-comment` (new): the requirement "The reason comment holds only the facts that the labels do not show".

## Impact

- 700 intake comments since 2026-11-06: the new rule removes 72% of their text (median 865 characters to 222). Only 1% of the items get no comment, because the model names a related item for 98% of the candidates.
- One GitHub read less for each candidate with no such fact.
- The comments already on the issues do not change.

## Feasibility

- The comment text comes from `_reason_lines` and `_comment` in `src/devops_cli/roadmap/intake/intake.py`. No other module reads it: the refine job treats a comment with the intake marker as the comment of a job, not as an answer.
- The 700 intake comments since 2026-11-06 (`devops gh api 'repos/{owner}/{repo}/issues/comments?since=2026-11-06T00:00:00Z' --paginate`) hold a Type and a Scope line in 688, a Priority, Value and Effort line in 700, a Related line in 687 and a Possible duplicate line in 8. The Priority is P2-Medium on 366 of the 433 open items with an intake comment (census of 2026-11-11), so P2-Medium is the usual Priority.

## Existing Tool Considered

No tool writes the reason comment of this project. Cost: about 40,000 tokens and 1 hour to build, about 1,000 tokens a month to keep, about 5,000 tokens to fix.
