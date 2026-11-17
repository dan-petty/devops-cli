# Proposal: #4960

## Why

The alternatives job sends the comments of other roadmap jobs to its model as person replies.
`_request` takes every trusted comment when the job left no comment, else every trusted comment
after its own comment. It drops no comment that holds a job marker. The intake reason comment is on
most new items and its author is trusted, so the model reads it as a person reply. A refine, stage
or retitle comment after the last alternatives comment reaches the model too. Closes #4960.

## What Changes

- A shared `comments_without_jobs` helper removes every comment that holds a marker of
  `CONST_ROADMAP_JOB_COMMENT_MARKERS`.
- `_request` calls the helper after the replies-after-marker selection and before the reply cap.
- Tests cover an intake comment with a person reply, and a refine comment after a check.

## Capabilities

### Modified

- `roadmap-alternatives`: the request holds only the comments of persons.

## Impact

The alternatives model reads person replies only. The cap counts person replies, so a job comment
cannot push a person reply out of the request.

## Feasibility

Confirmed against the issue and the code: `_request` in `src/devops_cli/roadmap/alternatives.py`
builds the replies, and refine's marker filter already removes the comments of other jobs (#2650).
The existing test helpers build the request from an in-memory store.

## Existing Tool Considered

No open tool or library covers the request of this job. The alternatives check of 2026-11-15
returned `none`, and its searches found no filter for job-marker comments. The change reuses the
project's own marker filter and costs about 30,000 tokens and one hour to build and keep.
