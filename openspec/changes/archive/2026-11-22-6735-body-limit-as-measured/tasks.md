# Tasks

## 1. Measure one text at open and at ready

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/open.py`, `src/devops_cli/github/merge_readiness.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/grounding.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_plan_check.py`.

- [x] 1.1 Write `test_a_body_that_starts_with_a_blank_line_gets_one_measure` in `tests/roadmap/test_roadmap_pull_form.py` first: for a text of 1,000 and of 1,001 characters after a blank line, `open_body_problems` and `body_problems` give the same length problems, and `measured_body_text` gives the known text. Add `test_a_line_that_the_form_takes_as_no_closes_line_stays_in_the_measured_text`, the same test for a plan body and `plan_body_problems`, and `test_a_body_that_starts_with_a_blank_line_at_the_limit_has_no_problem` in `tests/roadmap/test_roadmap_plan_check.py`. Each test imports the module `pull_form`, so it collects on the base, and fails there
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_plan_check.py`
- [x] 1.2 In `src/devops_cli/roadmap/pull_form.py` let `measured_body_text` split `body.strip()` and end the text at the first line that `_CLOSES_LINE` or `_PLANS_LINE` takes. Let `body_problems` and `plan_body_problems` give `_text_problems` the text of `measured_body_text`. Change the comment of `BODY_MAX_CHARS` and the docstrings of `open_body_problems`, `body_problems`, `measured_body_text` and `_text_problems` to name that text
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/steps/test_roadmap_step_open.py`
- [x] 1.3 Write `test_a_closes_line_with_whitespace_at_its_ends_ends_the_measured_text` in `tests/roadmap/test_roadmap_pull_form.py` and `test_a_plans_line_with_whitespace_at_its_ends_ends_the_measured_text` in `tests/roadmap/test_roadmap_plan_check.py` first: a `Closes` or `Plans` line with whitespace at its ends ends the measured text, the open step names only the missing `Closes` line, and the plan check finds no `body-length` problem for a text of 1,000 characters
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_plan_check.py`
- [x] 1.4 In `measured_body_text`, remove the whitespace at the ends of each line before `_CLOSES_LINE` or `_PLANS_LINE` takes it, as `plan_check.issue_number` reads the `Plans` line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/steps/test_roadmap_step_open.py`

- [x] 1.5 Write `test_a_marker_line_with_whitespace_at_its_ends_is_the_marker_line`, `test_a_padded_marker_line_above_the_marker_line_is_a_second_marker_line` and `test_each_reader_of_a_plan_body_takes_the_plans_line_by_one_rule` in `tests/roadmap/test_roadmap_pull_form.py` first: the form check takes a padded marker line, counts a padded `Plans` line above the `Plans` line as a second line, and the four readers of a plan body agree on each line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.6 Add `marker_issue` to `src/devops_cli/roadmap/pull_form.py` (strip, then match the whole line, with ASCII digits), and let `measured_body_text`, `_closing_problems`, `plan_body_problems`, `plan_check.issue_number` and `grounding.plan_blockers` take the marker line with it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_grounding.py tests/github/test_merge_readiness.py`

## 2. Compare the stage plan test with a known text

Kind: other. Changes: `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 2.1 Remove the top-level import of `measured_body_text` from `tests/roadmap/stage/test_roadmap_stage_plan.py`, and let `test_a_body_that_fills_its_room_gets_no_rewrite` find the `Plans` line of the body at index 1,000
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`

## 3. State the limit as the checks measure it

Kind: other. Changes: `src/devops_cli/commands/pr.py`, `docs/commands/pr.md`, `docs/commands/gh.md`.

- [x] 3.1 Change the help text of `devops pr create` in `src/devops_cli/commands/pr.py` to say that the text above `Closes` has at most 1,000 characters, and generate `docs/commands/pr.md` and `docs/commands/gh.md` again with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
