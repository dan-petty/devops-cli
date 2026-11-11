# Tasks

## 1. The kind of a left-out reason in the metric and the log (behavior)

- [x] 1.1 Write failing tests: each left-out item of the selection carries its kind, a skipped item counts under the kind of its reason, and three rounds log the reason of one item once for each kind.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/stage/test_roadmap_stage_job.py`
- [x] 1.2 Add `LeftOutKind` and `log_left_out` in `src/devops_cli/roadmap/stage/stage_left_out.py`, give each check of `_Judge` its kind, add `skipped_reasons`, and add the label `reason` and the log call to `emit_stage_results` in `src/devops_cli/roadmap/stage/stage.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/stage/test_roadmap_stage_job.py`

## 2. Documents (other)

- [x] 2.1 Name the label `reason` in the counter description of `src/devops_cli/telemetry/instruments.py`, write `docs/TELEMETRY.md` again with `uv run devops docs generate`, and name the label and the log line in `k8s/README.md`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
