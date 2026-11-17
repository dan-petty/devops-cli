# Proposal: #6199

## Why
The owner rule of #6193 is that no job posts the same content two times to an issue or a pull request, and that content in the body of an issue is not also in a comment (#6199). Three writers break the rule:

- `devops ci job-time --file-issue` files the alarm issue with the report as its body. Each later daily run over the limit posts the same report as a new comment, with no repeat guard.
- The `watch` row keys its conflict comment on the first 12 characters of the head commit. Each new conflicted head posts a new comment with the same advice, and the old ones stay.
- `devops review pr --post` posts all the findings as a new comment on each run, with no marker and no key, so a rerun on the same head posts them again.

## What Changes
- `GitHubClient.update_issue_body` replaces the body of an issue in one `PATCH` of `issues/<number>`.
- `devops ci job-time --file-issue` writes its report between two marker lines in the body of the alarm issue. A later run reads the body, replaces only the report, keeps the alarm line and the text of a person, and posts no comment. A body that already holds the same report gets no change. The dry run lists the read and the `PATCH` of the body in place of the comment.
- The `watch` row keys the conflict comment on its marker alone. A conflict at a new head edits the one conflict comment in place with that head.
- `devops review pr --post` opens its comment with a marker that holds the head commit. A rerun on the same head edits that comment, or leaves it when it holds the same review. A new head gets a new comment, and the comment of the older head stays. The dry run lists the read of the comments, then a `PATCH` or a `POST`.

The three writes are observable behavior of devops commands and of the Service, so the change carries spec deltas for `ci-job-time`, `roadmap-watch-row`, `roadmap-pr-conflicts` and `review-pr-comment`.

## Capabilities
- `ci-job-time`: the alarm issue holds the report one time, in its body.
- `roadmap-watch-row`: one conflict comment for each pull request, edited in place.
- `roadmap-pr-conflicts`: the conflict comment requirements follow the one-comment rule.
- `review-pr-comment`: one review comment for each pull request and head commit.

## Impact
- A daily alarm run sends one `GET` of the issue and at most one `PATCH` of its body, in place of one comment.
- Existing comments stay on GitHub. An alarm issue that was filed before this change gets the report block at the end of its body, after its first report.
- The change fits one pull request.

## Feasibility
Confirmed against the source on `origin/main` at `ffa602fe0`:

- `src/devops_cli/ci/job_time.py` `raise_alarm` calls `client.create_issue_comment(repo, held[0], text)` for an open alarm issue.
- `src/devops_cli/github/client.py` has no method that `PATCH`es `issues/<number>`: `update_pull` `PATCH`es `pulls/<number>`.
- `src/devops_cli/roadmap/watch_row.py` `_apply_due_steps` calls `post(..., marker, head_sha[:12], note)`, and `steps.comment.post` matches a comment only when it holds both the marker and the key.
- `src/devops_cli/ai/review/runner.py` `post_pr_review_comment` calls `create_issue_comment` with no marker.
- The issue names a dead `watch_conflicts` in `src/devops_cli/roadmap/stage/pr_conflicts.py`. That premise is wrong: `git grep watch_conflicts origin/main` finds nothing, and #5906 (commit `85b15fa71`) deleted `src/devops_cli/roadmap/pr_conflicts.py` and its tests. The change deletes nothing for it.

## Existing Tool Considered
GitHub's REST API has no upsert of a comment or of a part of an issue body, and no maintained library adds one. The change reuses what the code base has: `steps.comment.post` for the conflict comment, `GitHubClient.list_issue_comments` and `update_issue_comment` for the review comment, as `github/pr_evidence.py` does, and the start and end marker pattern of `roadmap/alternatives.py` `_with_block` for the alarm report. The new code is one client method of 5 lines and one block helper of 7 lines: about 2k tokens to build and keep, less than an hour of elapsed time. The change deletes the comment write of `raise_alarm` and the head key of the conflict comment.
