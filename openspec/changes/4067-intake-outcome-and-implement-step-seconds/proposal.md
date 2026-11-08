# Proposal

## Why

Intake has no count of the candidates that it places, skips, fails or flags as duplicates. The implement job has no timer for the scoped checks, the publish step and the watch of the pull request checks. The scoped checks take about 3.5 minutes and the watch takes up to 3600 seconds, so nobody can see which of them is slow (#4067). This is wave 9 of the staging plan in the tracker #3027. #4058 (row seconds) and #4066 (step seconds, label scheme) are merged, and this change reuses both.

## What Changes

- Declare the counter `devops_cli_roadmap_intake_candidates_total` (unit `1`) in `src/devops_cli/telemetry/instruments.py` with the labels `repo` and `result`, and add it to `INSTRUMENTS` and `__all__`. The values of `result` are `placed`, `duplicate`, `skipped` and `failed`. Series count: 4 for each repository.
- `apply_intake` takes the required keyword `repo` and adds 1 for each candidate. `placed` is a candidate that intake wrote with no duplicate flag. `duplicate` is a candidate that intake wrote and the model flagged as a possible duplicate: the verdict of the model only flags, and intake still places it. `skipped` is a candidate with the outcome skip, or a candidate whose Item a person changed since the plan (`RoadmapItemChangedError`, no write). `failed` is a candidate whose write raised `GitHubOperationError`. A rate limit or a refused token goes on as an error, and the candidates after it count nothing.
- The intake round sends 0 for each of the four results of its repository before the first candidate, as `tool_metrics.start_run` does for the tool calls. The round does this in `_apply_round`, which the intake row and the webhook path share.
- The three callers of `apply_intake` outside the round pass the repository they hold: `intake_candidate`, `devops roadmap intake` and the deferral write of refine.
- Add `CHECKS`, `PUBLISH` and `WATCH` to `StepName` in `src/devops_cli/roadmap/failure.py`. The requirement "A step has a name" of `roadmap-failure-taxonomy` changes.
- Time three steps of the implement job with `observe_step` and the row `implement`: `checks` is each call of `_scoped_checks` with its fix rounds, `publish` is the first push of a Planned item (`_publish`) or the push with lease of a Staged item (`_push_with_lease`) after the checks passed, and `watch` is each call of `watch_pull`. A step that raises has the result `error`. A watch that returns a failed check, a conflict or a timeout and no exception has the result `error` too, so `observe_step` yields a small handle with `fail()`. The stage callers ignore the handle.
- `_push_passed` (the push when the job stops, and the checkpoint push of #3677) stays untimed on purpose, and the document says so.
- The change touches `src/devops_cli/roadmap/implement/implement_run.py` at `_scoped_checks`, `_push` and `_checks` only. It does not touch `_groups` or `_start`, which #3677 changes. The timing code is in small helpers, so the diff of the file is a few lines.
- Series count of the histogram for the implement row: 1 repository x 1 row x 3 steps x 2 results = 6 series. The histogram is exponential, which Prometheus 3 stores as one native histogram for each series, so the buckets add none. The phrase "times the histogram buckets" in the issue does not hold. With the stage row (10 series), one repository holds 16 series.
- Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate --sync-readme`. The rows state the series counts.
- Rollout: the change adds, removes, renames and tightens no setting. `Settings`, `RoadmapConfig`, `RoadmapImplementConfig`, `RoadmapStageConfig` and `ServiceConfig` have `extra="ignore"`, so a key that an older image does not know is dropped and is not an error. The change applies nothing to the cluster.
- The change carries spec deltas, because a metric of the Service is observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The intake outcome counter and the implement step samples are declared, documented and sent
- `roadmap-failure-taxonomy`: A step has a name

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/step_metrics.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/commands/roadmap.py`
- Documents: `docs/TELEMETRY.md` (generated)
- Tests: `tests/telemetry/test_roadmap_intake_implement_metrics.py` (new), `tests/roadmap/test_roadmap_failure.py`, `tests/telemetry/test_roadmap_stage_steps.py`, and the calls of `apply_intake` in `tests/roadmap/intake` and `tests/support/roadmap_intake.py`

## Feasibility

- Code read at origin/main `c56f7849`, no run of the Service and no model run (AGENTS.md rule 13). No merged change, open pull request or newer issue or decision does this work. #4066 (`ROADMAP_STEP_SECONDS`, `observe_step`, the labels `repo`, `row`, `step` and `result`) and #4061 (failure class) are merged. The code has no intake outcome counter and no `checks`, `publish` or `watch` step.
- `StepName` (`src/devops_cli/roadmap/failure.py`) has seven members. The text of `ROADMAP_STEP_SECONDS` already names the implement row and this issue.
- The implement sites in `src/devops_cli/roadmap/implement/implement_run.py`: `_scoped_checks` runs the checks and the fix rounds, and `_push` calls it and then `_publish` (Planned item) or `_push_with_lease` (Staged item). `_checks` calls `watch_pull` once and once more after each repair round. `watch_pull` returns a `WatchKind` and raises nothing for a failed check, so `observe_step` needs the handle for the result `error`.
- `apply_intake` has no repository: the `RoadmapStore` protocol and `IntakePlan` hold none. The callers hold it: `_apply_round` (through `_run_intake_adapter` and `_intake_one`), `intake_candidate`, `commands/roadmap.py` and `_file_deferrals` in `refine.py`.
- The runner Job exports its samples: `docs/TELEMETRY.md` says that a command flushes one OTLP batch at `shutdown()` and that a cluster job pod exports once when it exits. So the fallback of the issue (time the steps from the log of the Job) is not needed. The change does not test the export in a live Job: it makes no cluster change and no model run.
- The Service primes only the counters of `GLOBAL_METRICS` (`counter_series.py`), which are the `/metrics` path. An Instrument of `INSTRUMENTS` is not primed there, so the round sends the zeros itself.
- The Settings models ignore an unknown key (`extra="ignore"` in `src/devops_cli/config/settings.py`; only the AI task models forbid it). The change adds no setting.
- The tests of this change fail on origin/main for the right reasons: `apply_intake` has no `repo` keyword, the instrument is not declared, `StepName` has no `CHECKS`, and a run of the implement job sends no sample. One guard passes on the base: the first seven values of `StepName` keep their order.
- Precondition: the calls need a checkout of the repository. They need no network, no cluster and no model.

## Existing Tool Considered

The OpenTelemetry counter and histogram that `emit()` in `src/devops_cli/telemetry/instruments.py` already sends, the clock seam `devops_cli.core.clock`, and `observe_step` of #4066. No new library. The change adds one counter helper and one handle on the existing context manager, because three implement sites and the intake round need the same labels; a try and finally block at each site would repeat them. It deletes no internal code. The cost written by the issue: about 45k tokens and 2.5 hours to build, 3k tokens each quarter to keep, and 10k tokens and 0.5 hours to fix.
