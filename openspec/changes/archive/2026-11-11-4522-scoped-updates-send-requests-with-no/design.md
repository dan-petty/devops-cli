# Design

## Decisions
- `run_scoped_update` sets the row scope around the runner, not `ScopedRoadmap` in the Service. `run_scoped_update` knows the `ScopedUpdate` and its job, and also counts the job under that row with `_count_job`. Thus the job counter and the request series get their row from the same value, `update.job`.
- The scope encloses only the runner call. `_count_job` sends no model or GitHub request, so its place does not change a label.

## Rejected alternatives
- Set the row in `ScopedRoadmap` (`src/devops_cli/server/service.py`): the Service would need to know the job of each event. That map is `SCOPED_UPDATES` in `run.py`, so a second copy of the job name could become different from the first.
- Set the row in `_intake_one`: each new scoped runner would need its own scope. A scope in `run_scoped_update` covers every runner of `SCOPED_UPDATES`.
