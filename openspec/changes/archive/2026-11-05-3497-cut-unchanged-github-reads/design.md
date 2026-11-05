# Design

## Decisions

### The status is a label of the request counter

The counter keeps its name and its total, and gains a `status` label. The issue allows a status label or a separate 304 counter. A separate counter would make the total the sum of two metrics. The read-only plan rejects it for that reason (plans/3497.json, key question 1).

### The request is counted after its answer

`acquire` no longer counts a request, because it runs before the request is sent and cannot know the status. `SessionGitHubAPI._request` counts each attempt after its answer, with the answer status `answer[0]`. A 304 therefore counts with status `304`. The token of an App is read inside that block, after the attempt is paced. An attempt that raises before an answer, a refused token included, counts with status `none` in a `finally` block, and the error still propagates. `run_gh` counts each paced attempt with status `none`, since gh does not report the HTTP status.

### The labels are read in the thread that paces the request

The request scope is a context variable. The session paces each request in a worker thread, so `pace_request` reads the request labels there, and `_request` carries them to the count. The labels are then the labels of the thread that sent the request, as the test `test_a_session_request_counts_the_scope_of_the_thread_that_sent_it` requires.

### A request that is not paced is not counted

`gh_request_is_paced` exempts `gh api rate_limit`, and `run_gh` skips `acquire` for it. The count follows the same rule, so an exempt request counts nothing, as before.

### The 304 charge stays

The limiter charges each attempt, a 304 too. ADR 0006 records that every attempt is paced and charged. The issue allows a charge of 0 only when a measure shows that GitHub does not count the 304. The local ledger has no such measure, so the charge stays and the metric keeps each 304 in its total.

### The pace lines log at DEBUG

Both pace lines write one record for each request that waits. The issue measured 53.6% of a log sample at INFO for these lines. A per-request detail belongs to DEBUG.

## Rejected alternatives

- A separate 304 counter: it makes the total the sum of two metrics (see above).
- Keep the count in `acquire` with status `none`: the status of the answer would be lost.
- A charge of 0 for a 304: no local measure shows that GitHub does not count it, and the ledger would undercount.
- Keep INFO: it keeps the log volume that the issue reports.
