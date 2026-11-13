# Tasks

## 1. The changed intake candidate

Kind: behavior. Changes: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/intake/test_roadmap_intake_job_result.py`.

- [x] 1.1 Write a failing test: the write of candidate 2 of 3 raises `RoadmapItemChangedError`, and the round logs the lines of candidates 1 and 3 only.
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_job_result.py`
- [ ] 1.2 Give `_count_candidate` the keyword `logged`, pass `logged=False` for a changed candidate, and say in the INFO line that another writer changed the Item.
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_job_result.py tests/roadmap/intake/test_roadmap_intake_item_changed.py tests/telemetry/test_roadmap_intake_implement_metrics.py`

## 2. The plan calls of a stage attempt

Kind: behavior. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_job_result.py`.

- [x] 2.1 Write failing tests: a plain client with no trace stages an item with `plan_calls=1`, and an attempt that stages a kept plan logs no `plan_calls`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_result.py`
- [ ] 2.2 Count the plan calls in `_ask_plan`, record a kept start in `plan`, write `plan_calls=None` for a kept start, and leave a None count out of `StageAttempt.counts`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_result.py tests/roadmap/stage/test_roadmap_stage_plan_record.py tests/roadmap/steps/test_roadmap_fix_plan.py`

## 3. Documents

Kind: other. Changes: `docs/roadmap/job-success.md`.

- [ ] 3.1 Add the changed intake candidate to the list "Some attempts write no line", tell when a `stage` line has no `plan_calls`, and say that a line with no count of the first-pass rule is no first pass. Regenerate the documentation with `devops docs generate`.
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- Pending a person: after the release and the deploy, check that Loki holds 0 intake result lines with `class=head_moved` in 24 hours, and that `devops roadmap eval grades --window 24h` shows intake with no `head_moved` class. Then add the live proof comment that #5166 asks for.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
