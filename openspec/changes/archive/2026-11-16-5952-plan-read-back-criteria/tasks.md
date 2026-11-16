# Tasks

## 1. Criteria read back

- [x] 1.1 Write failing round-trip tests with the criteria of #2202, #3655 and #3671 as group entries with a reason, a criterion with a line break, and the property strategy with a group reason and spaced texts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py`
- [x] 1.2 Move `one_line` to `stage_criteria.py`, fold the texts of `StageCriterion` and drop the reason of a group entry
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py`

## 2. Work that names the documents command

- [x] 2.1 Write failing tests for a work and a documents task that name `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py`
- [x] 2.2 Read the second task of a case-first group as its work, and cut the documents step only from the end of a documents task that `regenerates_documents` gives one
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py`

## 3. Record of a difference

- [x] 3.1 Write failing tests for `read_back_differences` and the log line of `read_back_error`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_failure_class.py`
- [x] 3.2 Add `read_back_differences`, log each difference in the stage job and put the records in the details of the error
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_failure_class.py`

## 4. Documents

- [x] 4.1 Describe the log line in `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs`
