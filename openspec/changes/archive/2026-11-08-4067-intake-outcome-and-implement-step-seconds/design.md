# Design

## Context

#4066 declared `devops_cli_roadmap_step_seconds` and `observe_step` for the stage row, and wrote that the implement row uses the same four labels. The implement job runs the scoped checks (about 3.5 minutes), the push, and the watch of the pull request checks (up to 3600 seconds) inside one row, so the row seconds of #4058 hide the slow step. Intake counts the result of no candidate. Tracker #3027, wave 9.

## Decisions

- **One histogram for both rows, with the labels `repo`, `row`, `step` and `result`.** The implement row passes `row="implement"`, taken from the name of the implement row and not from a new literal. The `step` values are `StepName` values.
- **`observe_step` yields a handle with `fail()`.** The result is `error` when the block raises, and also when the block calls `fail()`. The watch returns `WatchKind.FAILED`, a conflict or a timeout and raises nothing, but the issue wants `error` for a failed check. The stage callers ignore the handle, so their behavior does not change.
- **`checks` is one sample for each call of `_scoped_checks`.** The call includes its fix rounds, because the method is the step that the issue names and a sample is one call. A stop or another error in the call is `error`.
- **`publish` times only the branch after the checks.** `_push` runs `_scoped_checks` first, so a timer around `_push` would count the checks twice. The timer covers `_publish` for a Planned item and `_push_with_lease` for a Staged item.
- **`watch` is a small helper around `watch_pull`.** `_checks` calls `watch_pull` twice (the first watch and the watch after each repair round); both go through the helper, so each watch is one sample. The helper marks the sample `error` when the kind is not `READY`.
- **The implement code stays out of `_groups` and `_start`.** #3677 changes both. The timing is in helpers (`step_metrics.py` and one small method), and the diff of `implement_run.py` is a few lines at three sites.
- **`_push_passed` stays untimed.** It is the push of a stop and the checkpoint of #3677. It is not the publish step of a finished item, and a sample for it would mix two meanings. `docs/TELEMETRY.md` says so.
- **`apply_intake` takes a required keyword `repo`.** The store and the plan hold no repository. A default would hide a caller that forgets it, and the project keeps no backward compatibility, so each caller passes it.
- **One result for each candidate.** `placed` and `duplicate` are candidates that intake wrote; `duplicate` is the ones with `possible_duplicate` set. The model verdict only flags (owner rule of 2026-10-25), so a duplicate is placed, and the counter still names it. `skipped` is the outcome skip and the item changed by a person: nothing is written, and the next plan decides again. `failed` is `GitHubOperationError`. A rate limit and a refused token go on as errors and count nothing for the rest of the round.
- **The zeros start in `_apply_round`.** The intake row and the webhook path both call it, and it runs before the conditional `apply_intake`, so a round with no write still sends the four zeros. The Service primes only the `GLOBAL_METRICS` counters, so the round sends its own, as `tool_metrics.start_run` does.
- **Series counts are in the text of the instruments.** The intake counter says "4 series" (1 repository x 4 results). The step histogram says that the implement row adds 6 series (3 steps x 2 results) and that the stage row adds 10. `docs/TELEMETRY.md` is generated from those texts.

## Rejected Alternatives

- **A timer around `_push`.** It includes `_scoped_checks` and makes the `publish` and `checks` samples overlap.
- **One sample for each scoped check run.** The issue names three steps and six series. A second sample for each run breaks the count and the meaning of a call.
- **`error` on an exception only.** A failed check of the pull request would look like a success and hide the broken step.
- **A new histogram for the implement row.** A second metric needs a second dashboard query. The label `row` already separates the rows.
- **Read the repository from the store inside `apply_intake`.** The `RoadmapStore` protocol holds no repository, and a new member on the protocol touches every store and fake for one label.
- **Time the steps from the log of the Job.** The Job exports its samples when it exits (`docs/TELEMETRY.md`), so the fallback is not needed.
- **Send the zeros from the Service counter priming.** That path covers the counters of `GLOBAL_METRICS` for `/metrics`. An Instrument of `INSTRUMENTS` is not in it.
