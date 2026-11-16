# Design

## Decisions
- **Unit record.** `fix_checks.units` holds a JSON object, keyed by `<pr>:<head>:<check>`, of `attempt`, `outcome` and `retry_at` (epoch seconds, 0 for no wait). The round writes it when it reports a Job, before the annotation `roadmap.devops-cli/outcome`: a write that fails leaves the Job unreported, so the next round writes it again. The write reads the item first, so it keeps the units of other pull requests. A unit of the same pull request on another head goes, and at most 8 units stay. The watch row gives each `FixDue` the record text that its listing read, so a unit with no Job costs no read.
- **Last attempt.** `_last_try` takes the later attempt of the last Job and of the record. A unit with no Job uses the record alone.
- **No record in mode `plan`.** ADR 0021, rule 5: mode `plan` writes nothing to GitHub. A plan Job runs no model and ends in minutes, so a new plan Job after the TTL costs little.
- **One Job for each pull request (option 2 of the issue).** The round starts no unit for a pull request whose fix Job runs or waits. The unit key keeps the check, so `--check`, the unit name and the step key `<head>:<check>` agree (#5027). A second failed check of the head gets its unit after the first Job ends with no repair. A unit for each `<pr>:<head>` (option 1) would end the head after a first Job that stops, so a second check of that head would get no Job.
- **Wait limit.** `roadmap.fix_checks.max_wait_minutes` defaults to 360, above the 240 minutes of the deadline cap of a running model Job, so a working watch row resumes each fix Job first. `model_slots` counts a waiting fix Job only while its repository is in `service.repos` and it is not stale; it takes `now` for the test. The round lists the fix Jobs of every repository already, so it deletes each stale one with no other list. A delete that the API refuses is logged, and the Job holds no place.
- **Delete policy.** The CEL admits the delete of a Job named `devops-cli-fix-checks-*` with the component `roadmap-fix-checks` and `spec.suspend` true. A fix Job that runs stays protected.
- **Round errors.** The watch row catches `KubernetesError` (with `ClusterJobError`) and `ConfigurationError` around the round, logs a warning, and counts `round_error`. A GitHub error of the record write goes up, as the other GitHub writes of the row do.
- **Deadline.** A Job with no result line and the condition reason `DeadlineExceeded` has the outcome `deadline`. The result line still goes first.
- **Ready path.** `run_fix_checks(..., ready_only=True)` gives `skipped` when the head has a failed check. The watch row always passes it.
- **Panel.** Started (created, resumed), Repaired (repaired, ready), No result line (none, error, deadline), and Other for each other result, each with a fixed legend, as the panel "GitHub quota" of `devops-cli.json` does. No builder makes this dashboard; the SRE builder of #4675 makes the service dashboards under `k8s/monitoring/dashboards/`.

## Rejected alternatives
- **A longer TTL for fix Jobs.** The runner template sets `ttlSecondsAfterFinished: 86400` for every runner Job, and a longer TTL only moves the reset.
- **The record in Valkey.** The issue asks for the item record, and the step records `fix_checks.*` there already. Valkey holds no state of the watch row yet.
- **A record write when the round creates a Job.** It doubles the GitHub writes. The Job holds its attempt until the round reports it; only a Service that is down for 24 hours loses one attempt.
- **`topk(3, ...)` on the panel.** In a range query, `topk` takes the top 3 at each step, so the panel can still draw more than 3 series.
- **Resume a stale Job.** Only the watch row of its own repository resumes a Job, which is the cause of defect 3.
