# Tasks

## 1. Add the false-premise case and its test

Add the plan of PR #3408 at commit `1e7c3bbe` as a case of the golden set, and assert the case in the tests of the verification eval.

- [x] 1.1 Add `tests/fixtures/roadmap_eval/stage/3408-a-plan-restates-the-missing-path-rule/` with `case.json`, `facts.json`, `issue.txt` and `plan.json`. The case holds one `false_premise` defect with the gate `none`, and its evidence is the exact design line and the exact `missing_path` bullet of the prompt at the base commit `4e0e2435`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py`
- [x] 1.2 Add a case to the reviewed plans of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Add two tests to `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`: one asserts the defect, its evidence and the citation of the prompt, and one asserts that only a `false_premise` finding finds the defect
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py tests/roadmap/stage/test_roadmap_stage_eval_cases.py`
- [x] 1.3 Add the case to half B of `tests/fixtures/roadmap_eval/stage/split.json`. Set the counts of the whole set to 57 cases and 318 labelled defects in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py` and `tests/commands/test_roadmap_eval_screen.py`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py tests/roadmap/stage/test_roadmap_stage_screen_eval.py tests/roadmap/stage/test_roadmap_stage_eval_command.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py tests/commands/test_roadmap_eval_screen.py`
- [x] 1.4 Run the checks of the pull request
  - Verification: `uv run devops ci`
