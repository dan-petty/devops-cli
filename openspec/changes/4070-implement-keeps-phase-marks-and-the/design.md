# Design

## Decisions

- **Phase marks hold the head, not a flag.** `implement.checked_sha` and `implement.published_sha` hold a sha. A flag would stay true after a fix step or a rebase moved the head. A sha is stale at once when the head moves, so the check is one comparison with `_head()`. `_push_with_lease` already skips the `git push` when `origin/<branch>` equals the head. The mark adds the skip of the scoped checks, and the proof for a person that the head was pushed.
- **Order in `_push`.** `_sync` first, because it can move the head. Then the scoped checks unless `checked_sha` equals the head. Then `checked_sha` is written. Then the publish or the lease push unless `published_sha` equals the head, and `published_sha` is written. `_repair_after_push` calls `_push` again after a fix, so both marks refresh with the new head.
- **Two writes, not one.** Each phase mark is its own write. A Job can be killed between the checks and the push, and then the next Job must know that the checks passed. One write for both marks would lose that fact. The cost is two reads and two writes of the item (4 requests).
- **The run id is `implement.job`.** The Service writes the name of the runner Job before it makes the Job, so the runner needs no new channel. A Job with no value uses `manual`. The marker is a second line, so the first line (matched by `startswith` in `retry_asked`, and by `stop_clear.py` and `retitle.py`) does not change.
- **One comment for each run, updated in place.** The Job lists the comments once and keeps the id of the comment with its marker. The first write posts, and the later writes update. The body of an update is the table of all steps of this Job, so it replaces the earlier body without a loss. A Job with nothing to show writes nothing. The comments of the earlier Jobs stay as they are, each with its own run marker. `_comment` loses its `since` parameter and `last_comment_mark`, because every write now shows the whole Job.
- **The spend is a sum.** `_start` reads `implement.spend` and keeps it as the spend of the earlier Jobs. `_item_spend()` and `_spend()` add it to the spend of this Job: the requests, the input and output tokens, the steps and the tiers. The group mark carries `_spend()`, so a kill loses at most the group that ran. The shape of the JSON does not change, so a record of an older version loads.
- **A person retry clears the spend; a Service clear does not.** A person retries a stop on the item budget by a comment. If the spend carried on, the item would stop again at once. The Service removes `implement.stopped` before it continues a Job, so `target.retry` is false then, and the spend carries on. This is the rule that `_start` already uses for the other marks of a stop.
- **The progress line uses the callback of `monitor_pr`.** `watch_pull` passes a function that prints one line for a poll with a check that runs, after the first poll. No new loop, no new setting, and the stall limit stays.
- **`GROUP`, `SHA` and `WIP` stay.** The spec requires them as a record for a person, and removal would break the spec. The invariant test names a reader or a spec line for each key, so the next key that nothing reads shows up in a test.

## Rejected alternatives

- **Keep the comment in the pull request body.** The body is the squash message of the merge, and AGENTS.md says that test results and history go in a comment. Rejected.
- **A marker for the whole item, not for the run.** One comment for the item would need a merge of the table of each Job into one body. A Job would read and rewrite the rows of the earlier Jobs, and a failed update would lose them. A comment for each run loses nothing: the earlier comment is never written again.
- **One mark for both phases.** Rejected, see "Two writes, not one".
- **Skip the checks when the tree is clean.** Git cannot say that the scoped checks passed. Only the job knows, so the job records it.
- **A new setting for the interval of the progress line.** The poll interval already exists. A second interval would be a second number for one wait.
- **Remove `GROUP`, `SHA` and `WIP`.** Rejected because the spec requires them. See the decision above.
