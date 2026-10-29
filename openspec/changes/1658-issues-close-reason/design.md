# Design

## The order of the requests

`RoadmapStore.close(number, reason, comment=None)` reads the issue, posts the comment, then closes the issue. The read comes first, so a pull request, a missing issue or a closed issue gets no comment. The comment comes before the close, so the evidence is on the issue when it closes, and a failed close leaves the evidence.

When the close fails after the comment, the store raises `GitHubOperationError` whose message says that the comment is on the issue and that the issue is still open. Running the command again without `--comment-file` closes it with no second comment.

Rejected: close first, then comment. A failed comment would leave a closed issue with no evidence, and the issue would show no reason in its timeline.

Rejected: retry the close inside the command. The rate limiter already retries a throttled request, and a retry of a refused write would only repeat the refusal.

## One write path

The close is one `PATCH` of `repos/{repo}/issues/{number}` with `{"state": "closed", "state_reason": "<reason>"}` on standard input: `issue_edit_args` and `run_gh`, as each issue write of the store is. `StoreRequests.close` builds the dry run's requests from the same builders, so the plan and the run cannot drift.

Rejected: `-f state=closed -f state_reason=...` flags. Every other issue write of the store sends JSON on standard input, and the plan helpers already render that form.

Rejected: a new request builder in `github/issues.py` beside `devops gh issues edit`. The store already reads, comments and writes issues, and its in-memory adapter gives the command's tests a fake with the same promises.

## Reasons

The command takes `completed` and `not-planned` and maps them to `CloseReason.COMPLETED` and `CloseReason.NOT_PLANNED`. Typer checks the value against the choices, so a wrong value exits 2 with Click's own message, which names the allowed values, before any request.

Rejected: `duplicate`. GitHub links the original only through `duplicate_issue_id`, which needs the original's ID, and a person closes duplicates (#2223).

## An issue that is already closed

GitHub ignores `state_reason` unless the state changes, so a `PATCH` cannot change the reason of a closed issue. The command refuses a closed issue and says to reopen it with `devops gh issues edit <number> --state open` first.

Rejected: reopen and close in one command. That adds a reopened event to the timeline without a person's choice.
