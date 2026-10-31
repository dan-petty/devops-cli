# Tasks

## 1. The measure of a group counts the files its step reads

- [x] 1.1 Add failing tests: a file that a task names counts at most the file cap of the step; a file that only `reads` lists costs nothing; a file that a task names counts though `reads` omits it; the section of files of the step holds the packed text that the measure counts
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_measure.py`
- [x] 1.2 Add `roadmap/step_files.py` with the parser of `tasks.md`, `named_files` and `packed_file`; make `implement_step` and `stage_change.measure_groups` use it; delete `_packed`, `_packed_tokens` and the `limit` argument
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_implement_step.py`

## 2. A stop record counts only for the measure that made it

- [x] 2.1 Add failing tests: a stop record with the file cap of now stops the item; a record with another cap or none does not; the stop writes the cap; staging clears it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_apply.py`
- [x] 2.2 Add the record key `stage.file_cap`, write it with `stage.needs_split`, clear it on staging, and read it in the check of the recorded split
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_apply.py`

## 3. Documents

- [x] 3.1 Say in the module text of `stage.py` what a group costs and which record counts, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`
