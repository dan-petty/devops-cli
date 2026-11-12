# Tasks

## 1. A store refuses a repeat of a job's recent comment (behavior)

- [x] 1.1 Write failing tests: the same text at a new commit is refused, a changed fact posts, a person's reply or another job's comment ends the run, a repeat 7 days later posts, the counter counts by the row of the job, and both stores refuse the repeat.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_comment_repeat.py tests/roadmap/stores/test_roadmap_store_contract.py`
- [x] 1.2 Add `comment_repeat.py`, call it from the comment path of both stores, add the counter, add the implement marker to `CONST_ROADMAP_JOB_COMMENT_MARKERS`, and list the comments read in the request plan.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_comment_repeat.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_retitle.py`

## 2. A stop after each write leaves no second comment (behavior)

- [x] 2.1 Write failing tests: refine and the stage return run with a stop after each write, then again, and leave no comment that a whole run does not leave.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_write_stops.py tests/roadmap/stage/test_roadmap_stage_write_stops.py`
- [x] 2.2 Add `stop_after_each_write` in `tests/support/write_stops.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_write_stops.py tests/roadmap/stage/test_roadmap_stage_write_stops.py`

## 3. Documents

- [x] 3.1 Regenerate `docs/TELEMETRY.md` for the counter, name the harness in `docs/TESTING.md`, and state the guard in `docs/roadmap/refine.md`.
  - Verification: `$ uv run devops ci docs`

## 4. A refused refine repeat starts the wait at its round (behavior)

- [x] 4.1 Write failing tests: each change of a cited path gives one model call when the new look finds the same wait, `comment` returns whether it posted, and the dry-run plan lists the record of a refused repeat.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cited_paths.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 4.2 Return whether `comment` posted, record `refine.repeated_at` after a refused refine comment, start the wait at the later of that time and refine's last comment, list the record in the request plan, and state the mark in `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine tests/roadmap/stores`
