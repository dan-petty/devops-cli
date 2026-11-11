# Design

## Decisions

- The label holds the kind of the reason, and not the text. The text holds item numbers, times and counts, so it is not bounded. The kind is one value of `LeftOutKind` for each check of `_Judge`.
- A log line repeats only when the kind changes. The text of `queue_full` and `failed_lately` changes with counts and times, so a key on the text would log the same reason in each round.
- An item that the round handled with another result loses its logged kind, so a later reason logs again. An item that the round did not judge (past the limit) keeps its kind.
- The logged kinds are in a dict of the process with a lock and a public reset (`reset_left_out_log`), which the test floor calls.
- `LeftOut.kind` does not take part in the comparison, so two left-out items compare by their text as before.
- `reason` is on each point, with `none` for a result other than `skipped`, so each series of the counter has the same label names.

## Rejected alternatives

- A reason record in the job record of each item: each change of a reason makes a GitHub write in the round, and the Service already reads the record only to judge. The log line and the metric need no write.
- A log line for each left-out item in each round: 72 rounds in 48 hours for each repository give 72 lines with the same text for each item, which the issue names as noise.
- A label with the text of the reason: the text holds numbers and times, which make an unbounded set of series.
