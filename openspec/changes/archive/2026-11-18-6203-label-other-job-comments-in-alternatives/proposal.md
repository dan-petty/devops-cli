# Proposal: #6203

## Why
The alternatives request drops the comments of other roadmap jobs.
Commit e6f571827 removed every comment with a job marker to keep them out of person replies.
The alternatives model gets no refine proposal, intake reason, or failure report.
This conflicts with the rule that jobs must not miss context.
Closes #6203.

## What Changes
- `item_comments.py` adds a shared filter that classifies comments of roadmap jobs and labels each comment with its job name.
- `HeldComment` holds the job name when a comment comes from a roadmap job.
- `item_comments.py` adds `AlternativesJobForm` to format and fit job comments.
- `alternatives.py` builds the request with person replies in `replies` and other job comments in `job_comments`.
- `AlternativesTools` adds the `read_comment` tool so the model can read older indexed comments.
- Tests verify that job comments keep their job labels, person replies stay separate, and `read_comment` reads indexed comments.

## Capabilities
### Modified
- `roadmap-alternatives`: the request keeps comments of other roadmap jobs in `job_comments` labeled by job, keeps person replies in `replies`, and provides `read_comment`.

## Impact
The alternatives model reads refine proposals, intake reasons, and failure reasons of previous attempts.
Person replies remain separate and are not pushed out by job comments.

## Feasibility
Confirmed against the codebase.
The job markers exist in `COMMENT_JOBS` and `CONST_ROADMAP_JOB_COMMENT_MARKERS`.
The comment fitting window exists in `item_comments.py`.
`CommentReader` already provides `read_comment`.

## Existing Tool Considered
No open tool classifies project job markers or builds this request format.
The change uses existing modules `item_comments.py`, `alternatives.py`, and `stores/comment_repeat.py`.
Cost: about 3,000 tokens and 1 hour.
