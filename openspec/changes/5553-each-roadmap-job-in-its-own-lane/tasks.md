# Tasks

## 1. Behavior: one lane for each row

- [x] 1.1 Write failing tests: a blocked stage round lets a refine round of the same repository run and end; the default lanes are the rows of `DEFAULT_DUE_TABLE`, and `service.lanes` groups rows; the setting refuses a row in two lanes, an empty lane and a bad name, and `service_lanes` refuses an unknown row and a lane name of another row
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_lane_table.py tests/config/test_service_lanes_setting.py`
- [x] 1.2 Add `ServiceConfig.lanes`, `service_lanes`, `lane_of_row` and one job for each lane in `service_jobs`; delete the three lane constants
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_lane_table.py tests/config/test_service_lanes_setting.py tests/roadmap/test_roadmap_run_service.py`

## 2. Behavior: the clone and the snapshot of each lane

- [x] 2.1 Write failing tests: two lanes never use the same clone, and a change in the clone of one lane stays after a round of the other; each lane reads through its own snapshot and the intake lane through `listing`; the start removes the clones and the snapshots of lanes that the Service does not run
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_retire.py`
- [x] 2.2 Give each lane its clone `lanes/<lane>` and its snapshot, add `retire_lane_state` and call it in `devops serve --service`; delete `CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME` and the parameter `clone_dirname` of `service_job`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_retire.py tests/roadmap/test_roadmap_run_service.py`

## 3. Behavior: triggers, scoped updates and telemetry

- [x] 3.1 Write failing tests: two triggers with subjects coalesce into one batch with both subjects; a delivery names its issue as the subject; a scoped intake runs on the lane of `intake` and a critical placement wakes each other lane; a Service round sends `devops_cli_roadmap_row_seconds` with its lane; the counters start at zero under the lane that the setting gives a row
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_run_scoped_update.py tests/telemetry/test_roadmap_row_seconds.py tests/telemetry/test_service_counter_series.py`
- [x] 3.2 Add the subject to the trigger and `TriggerBatch.subjects`, run the scoped update on the lane of its row, send the lane to the row seconds, and prime the counters from `service_lanes`
  - Verification: `$ uv run devops ci test tests/server/ tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_webhook_keys.py tests/roadmap/test_roadmap_run_job_counts.py tests/telemetry/test_roadmap_row_seconds.py tests/telemetry/test_service_counter_series.py`

## 4. Documents

- [ ] 4.1 Update the lanes in `CONTEXT.md`, `docs/CLUSTER.md`, `docs/roadmap/intake.md`, `docs/roadmap/stage.md`, `docs/roadmap/alternatives.md` and ADR 0017, and regenerate the generated documents
  - Verification: `$ uv run devops docs generate && uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release rolls the Service image, check in Loki that refine rounds of devops-cli start at their interval while a stage round runs, and that the queue lines of #5470 show each row due on its own cadence. Check the largest working set of the first day against the limit of 3 GiB, and the use of the volume.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
