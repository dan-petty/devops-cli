# Design

## Decisions

- **The issue holds the stop report.** Only the comments of the issue reach the models (`item_comments.held_comments`) and `retry_asked`. So the stop comment on the issue keeps the whole report, and the comment of the run on the pull request keeps only what the issue does not hold: the amendments, the skipped steps, the scoped runs, the strength and check lines, and the comments that the steps read. The table of the stop comment holds every row of the table of the run, so the comment of the run drops its table on a stop and keeps it on a finished run.
- **The issue comment comes first.** The comment of the run links the page of the stop comment, so the job posts on the issue before it writes the comment of the run. A store that does not know the page gives None, and the link names the page of the issue.
- **The store gives the page and keeps the truth value.** `comment()` gives a `PostedComment` with `url` and `posted`, and its truth value is `posted`. Refine and `steps/comment.py` test the answer for a post, so they keep their behavior with no edit of refine. The repeat guard gives the earlier comment (`refused_repeat`), so a refused repeat links the comment that holds the same text.
- **`PostedComment` is a protocol.** The GitHub store and the in-memory fake each give their own value. The fake imports no new name of `src/`, so the fail-to-pass replay loads it against the base tree.
- **The report of a Job is for a Job with no result.** A runner that wrote its result wrote its own comment: the finished comment, the stop comment, the claim comment or the return comment. The round still reads the log and the item before it decides, so a stop that the runner writes in that time keeps its class (#3476). The record keeps the state and the digest of the Job.
- **The review keeps its verdict at one place at each time.** The step posts the verdict on the pull request first, as before, so a discard that stops halfway leaves it there. After the return comment on the issue holds the verdict, the step changes the comment of the pull request to a link. A later call that ends a discard on the closed pull request has no verdict, so it leaves the comment of the pull request as it is.

## Rejected alternatives

- **`comment()` gives the URL only, as the issue says.** A refused repeat also gives a URL, so refine could not tell a post from a refusal and would never record `refine.repeated_at` (`refine.py`, "A refused refine repeat starts the wait at its round").
- **A concrete `PostedComment` class in `store.py`.** The fake would import it, and the base tree of the fail-to-pass replay has no such name, so every test that uses the fake would fail there.
- **Read the comments of the issue after the post to find the page.** It costs one more listing for each stop, and GitHub already gives the page in the answer of the post.
- **Post the review verdict on the issue before the discard.** A failed delete or close would leave a verdict on the issue for a discard that did not happen, and two issue comments for one discard.
- **Keep the Job report and cut its log.** The log tail is the same text as the end of the runner comment, and a cut drops context (owner rule of 2026-11-17).
