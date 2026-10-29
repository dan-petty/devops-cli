# Proposal

## Why

Issue #2009, the first part of #1533: ADR 0003 makes polling the source of truth and a webhook only a hint. Each delivery that the roadmap consumer accepts makes a whole round of every due job, so an opened issue waits for, and pays for, that round. No roadmap code can run the update of one event alone, and nothing records what such an update handled.

## What Changes

- A new ADR, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`, supersedes the webhook clause of ADR 0003, and ADR 0003 points to it. It states the owner rule of 2026-10-09: each consumer declares the events that it subscribes to and the tasks that it runs on a schedule.
- `src/devops_cli/roadmap/run.py` gets the scoped updates:
  - `WebhookDelivery`: the repository, event, action and issue number that a delivery carries.
  - `SCOPED_UPDATES`: `issues` `opened`, `edited` and `reopened` run intake of the one issue, on the model lane.
  - `run_scoped_update`: runs the update of a delivery, or returns None for an event or action with none.
- Scoped intake runs intake's own decision code through `plan_intake(issues=(number,))`. It writes no job's last success to `schedule.json`.
- `IntakeRecord.merged` adds the decided issue to the intake record and keeps every other entry. The intake job reads the same record, so the poll does not decide that issue again.
- `IntakePlan.others_fresh`: a run over `issues` with a `waiting` record says whether a candidate it was not asked for is fresh. Scoped intake then keeps intake due, so the next poll decides the candidate of a lost delivery.
- No file under `src/devops_cli/server/` changes. The roadmap consumer gives each subscribed event to its scoped update in the second part of #1533.
- The scoped update is behavior that the roadmap jobs show, so the change carries a spec delta: the new capability `roadmap-scoped-updates`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-scoped-updates`: the update that a subscribed webhook event runs at once, scoped to its delivery, and the record that keeps the reconciling poll from doing it again.

## Impact

- `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/intake.py`.
- `tests/test_roadmap_run.py`.
- `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md` (new), `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`.

## Feasibility

- On origin/main `31b82cdd`, `plan_intake` takes `issues`, and a run over `issues` decides only the candidates among them (`_subjects` in `roadmap/intake.py`). An asked-for issue that is no candidate is reported as `missing` and decided by no one. This is the per-issue intake that `devops roadmap intake --issue` runs.
- The intake job writes `IntakeRecord.after(plan, now)`. It keeps only the entries of the candidates that the plan left, and sets `pending` from `fresh_left`. A plan over one issue leaves no candidate, so `after` would drop every other entry and clear `pending`. So scoped intake needs a merge, not `after`.
- `run_due_jobs` judges each row by the changes since its own last success in `schedule.json` (`_Poll.is_due`). Intake's due rule is a reopened issue or a `pending` record, and its interval is 60 minutes (`DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES`). An `opened` event is no `ChangeKind`, so the candidate of a lost `opened` delivery waits for that interval unless the record is `pending`.
- `GitHubWebhookPayload` (ADR 0009) declares `action`, `repository.full_name` and `sender.login` only, and the delivery target receives the repository, event and action. So this change takes the issue number as an input of `WebhookDelivery`, and the second part of #1533 reads it from the payload.
- The model lane runs intake and refine one at a time (`MODEL_LANE_ROWS`). Scoped intake runs on that lane, so it and the intake job never write the intake record at the same time.
- #1647 is closed as completed, and #2009 is the only child of #1533. No open branch holds this work.

## Existing Tool Considered

The ADR 0009 router already parses each event, and intake already decides one issue. The scoped update reuses both, and the intake record already says which candidate was decided at which `updated_at`. No library covers an event-scoped run of these jobs, so the change builds about 100 lines of glue in `roadmap/run.py` and `roadmap/intake.py` and no second set of job rules. It deletes no code.
