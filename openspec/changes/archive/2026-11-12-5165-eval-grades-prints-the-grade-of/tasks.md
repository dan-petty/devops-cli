# Tasks

## 1. Grade rules (behavior)

- [x] 1.1 Write failing tests for the grade table, the point grade, the range and `too few`
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade.py`
- [x] 1.2 Add `roadmap/job_grade.py` and `FIRST_PASS_LIMITS` in `roadmap/job_result.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade.py tests/roadmap/test_job_result.py`

## 2. Report and command (behavior)

- [x] 2.1 Write failing tests of the report on recorded Loki replies and of the command, with the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py`
- [x] 2.2 Add `query_loki_metrics`, `roadmap/job_grade_report.py` and `devops roadmap eval grades`, then run `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py tests/k8s/test_loki_url_setting.py`

## 3. Generated grade table (behavior)

- [x] 3.1 Write failing tests of the synced block of the job success page
  - Verification: `$ uv run devops ci test tests/docs/test_docs_synced_blocks.py tests/docs/test_docs_inventory.py`
- [x] 3.2 Sync the grade table in `devops docs generate`
  - Verification: `$ uv run devops ci test tests/docs/test_docs_synced_blocks.py tests/docs/test_docs_inventory.py`

## 4. Documents

- [x] 4.1 Replace the 80% rule section of `docs/roadmap/job-success.md` with "The job grades", add the term "job grade" to CONTEXT.md, and update `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- #5166 removes the intake lines of a candidate that another writer changed (`head_moved`) and counts the plan calls of stage.
- #5168 adds `first_pass` and the efficiency counts to each line, so each job can get the grade `100`.
- #5169 makes a Job pod and a local run send the line, and widens the base selector past the Service stream.
- #5173 makes the 80% rule the held-grade rule for each floor.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
