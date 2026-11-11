# Tasks

## 1. Refuse a requirement text over the OpenSpec limit

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_check.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_requirement_length.py`, `tests/roadmap/test_roadmap_plan_check.py`.

- [x] 1.1 Add `tests/roadmap/stage/test_roadmap_stage_requirement_length.py` and `test_a_requirement_over_the_openspec_limit_is_reported` in `tests/roadmap/test_roadmap_plan_check.py`: an ADDED and a MODIFIED text of 543 characters are refused with the name and the length, a text of 500 characters passes, and a character outside the Basic Multilingual Plane counts two. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirement_length.py tests/roadmap/test_roadmap_plan_check.py`
- [x] 1.2 Add `REQUIREMENT_MAX_CHARS`, `_js_length`, `_length_problems` and the message `stage_problem_requirement_long`, and call `_length_problems` from `_delta_problems`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirement_length.py tests/roadmap/test_roadmap_plan_check.py`

## 2. The #3462 plan is a golden case

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Changes: `tests/fixtures/roadmap_eval/stage/3462-a-modified-requirement-over-the-limit/case.json`, `tests/fixtures/roadmap_eval/stage/3462-a-modified-requirement-over-the-limit/facts.json`, `tests/fixtures/roadmap_eval/stage/3462-a-modified-requirement-over-the-limit/issue.txt`, `tests/fixtures/roadmap_eval/stage/3462-a-modified-requirement-over-the-limit/plan.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 2.1 Add the case with the plan of PR #4435 and its `spec_delta_wrong` defect at the gate `paths`, and raise the counts of the set: 58 cases, 53 reviewed pulls, `spec_delta_wrong` caught 7, judged 82 of 319
  - Verification: `$ uv run devops roadmap eval stage --replay`

## 3. Documents

Reads: `docs/roadmap/plan-recheck.md`. Changes: `docs/roadmap/plan-recheck.md`.

- [x] 3.1 Say in the gate table of `docs/roadmap/plan-recheck.md` that the gate `spec-delta` refuses a requirement text over the OpenSpec limit
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: `check_proposal` refuses an ADDED and a MODIFIED requirement text of 543 characters with the name and the length, and passes a text of 500 characters.
- Group 1: `devops roadmap plan-check` reports the problem with the rule `stage`.
- Group 1: One constant holds the limit, with a comment that names the OpenSpec rule.
- Group 2: The replay lists the #3462 case as caught by `check_proposal`, and exits 0.
