# Design

## Decisions

- **The draft of the run comes from the plan.** A Staged target carries the pull request that the plan checked; a Planned target, whose branch is gone, carries none. `prepare` writes that value, or clears the mark, so `publish` takes from the record only a draft of this run.
- **The lookup of `open_or_update` finds a draft that no mark records.** It is one GET for the head of the branch. A draft that it finds gets the title and the body, and the mark.
- **The withdraw is recorded as `publish` records a push.** `publish` writes `implement.published_sha` right after its push, and it now clears `implement.base` right after the withdraw.
- **The title of the issue gets the same check as the summary of the plan.** The problem goes into the stop message of a refused title.

## Rejected alternatives

- A check of the state of the recorded draft in `publish`: the plan reads that state already, and a second read adds a request.
- A retry of the delete of the withdraw: the branch that is gone needs no delete, so the record of the withdraw is the plain fix.
