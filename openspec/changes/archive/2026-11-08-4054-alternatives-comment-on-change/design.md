# Design

## Decisions

- **The compare is in `AlternativesWriter.settle`, after the guard `_unchanged_since_read` and before the comment.**: `settle` has the check, with the item as the job read it, and it writes the marks. The record of the earlier check is `check.item.job_record`. One private function `_result_changed(check)` returns true when the record holds no verdict, or when the recorded verdict or tool differs from the check.
- **A tool of `None` and a tool with a URL are different.**: A check that finds a tool where it found none, or finds none where it found one, is news.
- **The marks and the block are written in both cases, in the one request of #4049.**: The date moves, the item is not due again before the recheck days pass, and the order rule of #2951 stays. Only `store.comment` depends on the compare.
- **The metrics and `written` count a check with no comment.**: `devops_cli_roadmap_alternatives_total` and `..._searches` count checks, and a coverage view needs the count of rechecks that found no change.
- **The dry-run plan keeps the comment and adds the condition `check_changed`.**: A dry run makes no request and cannot read the record, so it lists the comment as a request that happens only for a first check or a changed result.
- **A comment of an earlier check stays the anchor.**: `replies_after_marker` reads the last comment with the marker. A person's reply after it is still read, and no code changes in refine.

## Rejected alternatives

- **Compare the text of the new comment with the text of the last comment.**: The comment holds the reason, the searches and the sources, which differ on each run of the model, so the text almost always differs and the thread would fill as before.
- **Post a short comment, "no change", for a same-result recheck.**: It keeps a comment with no news in the thread, which is the defect.
- **Skip the write of the block and the marks for a same-result recheck.**: `checked_at` would not move, so the item would be due on the next round and checked again with model spend.
- **Record the verdict and the tool in a new mark of the last comment.**: The record already holds both, and a second place for the same fact can drift.
