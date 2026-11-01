# Each subscribed webhook event runs the update scoped to it, and the poll reconciles

This ADR supersedes the webhook clause of [ADR 0003](0003-polling-is-how-the-roadmap-sees-changes.md), "webhooks only cut latency". The poll of ADR 0003 stays.

Before this decision, each delivery that the roadmap consumer of [ADR 0009](0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md) accepted made a whole round of every due job of the repository. An opened issue waited for that round, and paid for it. No roadmap code could run the update of one event alone. [ADR 0016](0016-labels-hold-the-roadmap-items-fields.md) moved the fields of an Item into labels, so a change of a field is now an issue event that the repository webhook sends. GitHub still never sends a failed delivery again, so the poll stays.

On 2026-10-09 the owner decided that each subscribed event runs, at once, the update scoped to it, and that the poll reconciles ([#1533](https://github.com/dan-petty/devops-cli/issues/1533)).

- **Each consumer declares its events and its scheduled tasks.** A consumer names the events that it subscribes to, and the tasks that it runs on a schedule. The roadmap consumer subscribes to the events of ADR 0009, and its scheduled task is the poll of ADR 0003.
- **A subscribed event runs the update scoped to it.** A scoped update runs the decision code of its job, narrowed to what the delivery carries. `SCOPED_UPDATES` in `src/devops_cli/roadmap/run.py` holds the table, and `run_scoped_update` runs one update:

  | Event | Actions | Scoped update | Lane |
  | :--- | :--- | :--- | :--- |
  | `issues` | `opened`, `edited`, `reopened` | intake of the one issue that the delivery names | model |

- **Another event stays a hint.** An event or an action that has no row in the table makes a whole round due, as before.
- **A scoped update writes no last success.** A scoped update never writes a job's last success to `schedule.json`. So the poll still judges every change made since the last round of each job, and a scoped update never hides a change that it did not handle.
- **A scoped update records what it decided.** Scoped intake adds the issue that it decided to the intake record, with the issue's `updated_at`, and keeps every other entry. The intake job reads the same record, so the poll does not decide that issue again. When scoped intake finds another candidate that is fresh, it keeps intake due, so the next poll decides the candidate of a lost delivery and does not wait for the interval of the row.
- **A scoped update runs on the lane of its job.** Scoped intake runs on the model lane, one item at a time with the intake job, so the two never write the intake record at the same time.
- **The poll stays every 151 seconds** (`service.poll_interval_seconds`). It finds a lost delivery and each change that no event scopes.

## Considered Options

- **Webhooks as the only trigger, with GitHub's recommended job that sends failed deliveries again**: rejected. GitHub never sends a failed delivery again by itself, and the job would be a second path to the result that the poll gives.
- **A scoped update writes the last success of its job**: rejected. The poll would then skip each change older than the update that the update did not handle, for example an issue whose delivery was lost.
- **A record of handled deliveries, by delivery id**: rejected. The intake record already says which candidate was decided, and at which `updated_at`. A second record could disagree with it.
- **A lane of its own for scoped updates**: rejected. Scoped intake and the intake job would then write the intake record at the same time.

## Consequences

- The roadmap consumer gives each subscribed event to its scoped update on the lane that the table names, queueing no full round (#1533). The live check, a real delivery of each subscribed event, waits until the Service runs again.
- A delivery of `issues` `edited` about an issue that is already an Item decides nothing.
- Intake's interval of 29 minutes stays for the candidates that no delivery names.
- The delivery target of ADR 0009 stays the one seam between the router and the jobs. A move of the delivery to another engine changes only that target.
