# Design

## Decisions
- **The alarm report is a block in the body.** `_with_report` puts the report between `<!-- devops ci job-time report: start -->` and `<!-- devops ci job-time report: end -->`. The block is the last start line and the first end line after it. When a person deletes one of the two lines, the next run adds a new block at the end, and no run replaces text of a person between an orphan line and a new line.
- **The alarm run reads the body again before it writes.** The issue search gives the body from its index, which can be older than the issue. `raise_alarm` reads the issue with `GET issues/<number>` and changes that body, so an edit of a person since the index stays. The run sends no `PATCH` when the body already holds the same report.
- **The issue body update is its own client method.** `update_issue_body` `PATCH`es `issues/<number>` with the body only. `update_pull` `PATCH`es `pulls/<number>`, which is not an issue endpoint.
- **The conflict comment uses the marker as its only key.** `post` with no key finds the one conflict comment on the pull request, and edits it when its text, which names the head, changes.
- **The review comment key is the full head commit.** The comment opens with `<!-- devops review pr: <head> -->`. `post_pr_review_comment` reads the comments of the pull request and edits the one that holds the marker of the head; with none, it posts a new comment. A review of a new head is a new review, so its comment is new, and the comment of the older head stays as the record of that review.

## Rejected alternatives
- **Use the body of the search hit for the alarm.** The search index can lag behind an edit of a person, and a `PATCH` from that body would drop the edit. One `GET` a day costs less than a lost edit.
- **Refuse to write when a block marker has no partner**, as `alternatives.py` `_marker_problem` does. The daily alarm would then stop writing its report until a person repairs the body. The last start line and the first end line after it give one block that never holds text of a person, so the run can still write.
- **Reuse `roadmap.steps.comment.post` for the review comment.** `ai/review` would import from `roadmap`, and #6197 and #6194 change `steps/comment.py` now. `github/pr_evidence.py` already writes its comment with the client calls, so the review comment does the same.
- **Edit one review comment for every head.** The rule of #6199 keys the comment on the head commit. A review of a new head holds other findings; an edit would remove the review of the older head from the pull request.
