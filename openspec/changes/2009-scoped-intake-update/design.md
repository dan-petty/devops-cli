# Design

## Context

The roadmap Service runs two lanes for each repository. Each accepted delivery and each poll queue a round on both lanes, and the round runs the rows that are due. Intake decides at most five candidates a round, fresh ones first, and keeps `IntakeRecord` beside `schedule.json`.

## Decisions

- **The table lives in `roadmap/run.py`.** `SCOPED_UPDATES` sits beside the due table, its one owner, as CONTRIBUTING.md says for a single-owner table. Each row names its job, its lane and its runner.
- **The delivery carries the issue number.** `WebhookDelivery` holds the repository, event, action and issue number. The scoped update reads the issue itself from the store, as intake does.
- **No last success.** `run_scoped_update` never writes `schedule.json`. The poll judges the changes since each job's own last round, so a change that the update did not handle stays visible.
- **The record is merged.** `IntakeRecord.merged` adds or replaces the entries of the decided issues and keeps the others. It sets `pending` when the record was `pending`, or when the plan saw a fresh candidate that it was not asked for (`IntakePlan.others_fresh`).
- **`others_fresh` is a field of its own.** `left` and `fresh_left` keep their meaning for a capped run, and the report of `devops roadmap intake --issue` stays the same. `others_fresh` is set only when the run has a `waiting` record, and only the scoped update passes one with `issues`.
- **The record is written only when it changes.** An edit of an Item decides nothing and finds no fresh candidate, so it writes no file.

## Rejected Alternatives

- **Write intake's last success after a scoped update**: rejected. The test with a lost `reopened` delivery shows that the poll would then skip the older reopen.
- **Use `IntakeRecord.after` for the scoped run**: rejected. A one-issue plan leaves no candidate, so `after` drops every other entry and clears `pending`. The capped-round test shows the loss.
- **A record of handled deliveries, by delivery id**: rejected. The intake record already holds the decision and its `updated_at`. A second record could disagree with it.
- **Change `left` and `fresh_left` for runs over `issues`**: rejected. The intake report prints `left`, so a person's `--issue` run would print candidates that it was never asked about.
- **A lane of its own**: rejected. Scoped intake and the intake job would then write the intake record at the same time.

## Risks

- The second part of #1533 must run the scoped update on the model lane, as the table says. A run on another lane races the intake job.
