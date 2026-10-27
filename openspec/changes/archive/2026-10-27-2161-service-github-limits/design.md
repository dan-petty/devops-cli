# Design

## Decision

`RoundPause` is the one object that every worker asks before it starts a round. It gets two more reasons to say no.

1. **Halt.** `after(exc, repo)` first asks the identity reader. `roadmap.run.identity_refused` is true for a `GitHubUnauthenticatedError`, found in a `RoadmapRunError` cause group too. The first refusal sets the halt, logs one error naming the machine account, and counts the metric. `holds()` is true for ever after. The Service stays healthy, so the orchestrator does not restart it and send more requests with a refused identity.
2. **Budget.** `RequestBudget` keeps the request count at each round end, for one hour. The requests of the last hour are the newest count minus the count at the newest sample at least one hour old. `holds()` is true when that number reaches the limit. `poll_interval` is `max(configured, window * rounds_per_poll * cost / limit)`, where `cost` is the mean requests of a round.

`_execute_due_rows` breaks out of its loop after a refusal, so a later job of the same round sends no request. It also asks a `FailureLedger`. A job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on one input is skipped. The input is the changes since the oldest last success, plus the time of the round when the batch holds a trigger that is not a poll. The Service shares one ledger, so lanes and repositories count apart by (repository, job).

## Rejected alternatives

- **Classify a 403 by the message in the session path.** `tests/test_github_errors.py` states that no HTTP case reads a message. The Service's refusal comes through `gh`, whose output the table already classifies by text.
- **Exit the process on a refusal.** The Deployment restarts it and the new process sends requests again. A halt that keeps the process alive and reports once is safer.
- **Set the budget by the primary rate limit headers.** The 5,000 an hour quota is shared by every client of the account, and the account was suspended far below it.
- **Keep the failure count on disk.** A restart is "a person restarts it", which resets the ledger on purpose.
