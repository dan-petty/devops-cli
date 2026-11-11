# Design

## Decisions

- **A new status-lane row, last.** The status lane runs its rows one at a time, and a row waits for the rows before it. The row reads GitHub once for each open pull request that is not a draft, so it goes after `cloudflare_status` and delays no other row. A failed read fails this row only, as the status reads do (#4052).
- **A comment, not a label.** A comment notifies the people who watch the pull request and needs no repository setting. A `pr/conflicted` label needs a label in each managed repository, sends no notification, and collides with the label families that hold the item fields (ADR 0016). `GitHubClient.comment_on_pull` posts the comment through the GitHub session.
- **No action for a clean pull request that is behind.** The issue design asked for an update-branch request. A catch-up update starts every required check again, and docs/SDLC.md (Phase 1) and the owner requirement of 2026-11-11 forbid it for an open pull request. GitHub merges a branch that is behind unless a ruleset requires an up-to-date branch, and the readiness verdict already treats `behind` as no blocker.
- **Read the candidates through the store and the session.** `store.open_pulls()` gives the open pull requests and their draft flag, so a draft costs no read. `GitHubClient.get_pull_status` reads the one pull request, and `PullStatus` now holds `mergeable`, `mergeable_state`, `base_ref` and `default_branch`. The listing holds no `mergeable` field, so the read of each candidate is necessary. `store.item` reads the one issue that the body closes.
- **A delivery pull request closes exactly one open Item.** `closing_numbers` of `release_feed.py` reads `Closes`, `Fixes` or `Resolves` at the start of a line. A plan pull request closes nothing, and the release pull request closes nothing, so the row skips them.
- **One conflict judgment.** `merge_conflict(mergeable, mergeable_state)` in `merge_readiness.py` returns True for a conflict, None for a state that GitHub has not computed, and False else. The readiness verdict, the implement watch and the row call it, so the three cannot disagree.
- **A ledger beside `schedule.json`.** `pr_conflicts.json` maps the number of each conflicted delivery pull request to the head commit of its comment. A round drops the entry of a pull request with no conflict, keeps the entry of an unknown state, and drops the entries of pull requests that it no longer judges. The round writes the ledger also when a read fails, so a comment that it posted is not posted again. This follows `release_comments.json`.
- **Interval 13 minutes.** GitHub computes the mergeable state after a read asks for it, so a new conflict shows within two rounds. A round costs about two reads for each ready pull request.
- **A gauge, no dashboard.** The row sends `devops_cli_roadmap_conflicted_pulls` by `repo`, as `record_coverage` sends the alternatives gauges.

## Rejected alternatives

- **Send `PUT pulls/{n}/update-branch` for a clean pull request that is behind.** Evidence: docs/SDLC.md, Phase 1: "A pull request that is open needs no rebase to catch up with `main`." The owner plan of 2026-11-11 counted 49 catch-up pushes that started runs in one week. The update also refuses a conflict, so it cannot fix the case that the row reports.
- **eps1lon/actions-label-merge-conflict.** It needs a workflow and a label in each managed repository, has no delivery filter, does not use the judgment of `devops pr check-readiness`, and sends no gauge.
- **Put the check in the `stage_ready` row.** A failed conflict read would then fail the row that marks drafts ready, and the row mixes two jobs.
- **Call `assess_merge_readiness` for each pull request.** It also reads the checks, the review threads and the changed files, which the judgment does not need.
- **One GraphQL query for all pull requests.** It needs a second definition of a conflict (the GraphQL enum names) and leaves the REST payload that `check-readiness` judges.
- **Find an earlier comment by a hidden marker instead of a ledger.** It needs a comment listing for each pull request, and it cannot tell a conflict that returns after a clean round at the same head commit.
- **Post the comment through `store.comment`.** The store writes comments on issues, and the in-memory store refuses a pull request number. The session client is the interface for a pull request comment.
