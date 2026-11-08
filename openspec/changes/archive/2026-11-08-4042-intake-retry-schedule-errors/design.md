# Design

## Decisions

- **Catch `RoadmapItemChangedError` in `apply_intake`, before `GitHubOperationError`, and log it at INFO.**: The error says that a person changed the Item and that nothing was written. The intake record already keeps every decided candidate, so the next round decides it again with the change. The claim code (`service_claim`) already reads the error this way.
- **Report the P0 placement in `IntakeApplied`, set by `apply_intake`.**: `_places_critical_or_p0(plan)` reads the plan, and a plan also holds decisions whose write failed or was refused. `apply_intake` is the one place that knows which decision was written, and a new candidate has no number until it is filed, so a list of numbers cannot name it. A counter of the critical or P0 decisions that were placed needs no number.
- **One function writes the stamp for both the intake job and the scoped intake.**: `_run_intake_adapter` and `_intake_one` end with the same eight lines. The helper applies the plan, writes the stamp when a P0 was placed, and only then calls `raise_for_failed_placements`. A fix in two copies would drift again.
- **The stamp comes before the raise.**: A real placement failure of another candidate must not hide the P0 that the round placed, because refine would then wait for its interval.
- **`_read_schedule` raises `RoadmapRunError` and names the file, as `read_intake_record` does.**: The reader has two callers. `run_due_jobs` reads it first, so a bad file stops the round before any row runs. `_record_success` reads it under `_SCHEDULE_LOCK`, so it never writes over a file that it could not read. A missing file stays empty, because a repository that never ran has none.
- **Add the message `run_schedule_unreadable`, with the path, the reason and the remedy.**: The text follows `run_intake_record_unreadable`, and the details hold the path.

## Rejected alternatives

- **Treat the unreadable file as empty and log a warning.**: This is the fault. At origin/main the reader returns `{}`, and every row with `first_run_due` runs at once with model spend. A warning does not stop it.
- **Rename or move a corrupt `schedule.json` aside and start a new one.**: It hides a fault that a person can see in the file, and it is the same first run for every row. The intake record has the same rule (#1360): raise and name the remedy.
- **Count the item-changed candidate as skipped in `IntakeApplied`.**: It would add a field that nothing reads. The record and the log line already show the candidate, and #4061 owns the count and the class of a placement.
- **Pass the numbers of placed candidates to the stamp.**: A new candidate has `number` None until it is filed, so the list is not complete.
- **Add a test that loads the example ConfigMap into `Settings`.**: The change removes, renames and tightens no setting, and `tests/config/test_k8s_devops_runtime.py` already does this for the example ConfigMap.
