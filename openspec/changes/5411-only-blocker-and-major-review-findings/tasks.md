# Tasks

## 1. Give each finding a severity and open only a blocker or a major finding

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_later.md`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/support/roadmap_fix_plan.py`, and each test that builds a finding.

- [x] 1.1 Write `test_a_minor_finding_is_advice`, `test_a_minor_placeholder_finding_is_advice`, `test_a_finding_with_no_severity_fails_the_schema`, `test_the_prompt_names_the_four_severities_and_the_two_that_return_the_plan`, `test_the_spec_delta_type_names_a_scenario_where_no_test_can_assert_any_part` and `test_a_minor_new_finding_of_a_later_review_is_advice` in `tests/roadmap/stage/test_roadmap_stage_verify.py`, `test_a_minor_finding_is_a_point_of_the_comment_and_applies_no_label` in `tests/roadmap/stage/test_roadmap_stage_verification.py`, and `test_a_minor_or_a_nit_finding_is_advice_and_refuses_nothing` in `tests/roadmap/refine/test_roadmap_refine_trust.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add the required `severity` to `Finding`, add `OPEN_SEVERITIES` and check it in `open_findings`, start the comment line with the severity, describe the four severities and the new `spec_delta_wrong` text in the prompts of the pass, and give each test that builds a finding a severity
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/refine tests/roadmap/test_roadmap_failure.py`

## 2. Read the severity back and list the advice in fix-plan

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [x] 2.1 Write `test_a_head_with_only_a_minor_finding_is_dismissed_and_lists_it_as_advice` in `tests/roadmap/steps/test_roadmap_fix_plan.py`, and `test_a_line_from_before_5411_names_no_severity_and_reads_as_major` with a blocker in `test_the_reader_reads_back_each_open_finding_and_no_point` in `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py tests/roadmap/steps/test_roadmap_fix_plan_comment.py`
- [x] 2.2 Read an optional severity in `_FINDING_LINE` and `_finding_of`, with major for a line with no severity, and add the advice of the reviews to the comment of a pushed revision or of a plan that loses the label
  - Verification: `$ uv run devops ci test tests/roadmap/steps`

## 3. Gate the findings that return a good plan in the eval

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_verify.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [x] 3.1 Write `test_the_report_gates_good_returning` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 3.2 Add `CONST_ROADMAP_VERIFY_GOOD_RETURNING_CEILING` with the reason of its value, `VerifyScore.good_returning_mean`, the ceiling line after the good line of the report and `good_returning_mean` in the JSON report; name the ceiling in the help of the command
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## 4. Describe the severity rule and the ceiling

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`.

- [x] 4.1 Describe the severity, the open rule, the comment line, the advice of `fix-plan` and the ceiling of the eval, and run `uv run devops docs generate`
  - Verification: `$ uv run devops docs check`

## 5. Score the pass and validate the rule on real plans

Kind: other. Reads: `tests/fixtures/roadmap_eval/stage/2166-the-unused-run-subprocess-re-import/case.json`, `tests/fixtures/roadmap_eval/stage/2169-the-qdrant-retry-the-process-fake/case.json`. Changes: none.

- [x] 5.1 Run `uv run devops roadmap eval verify --case 2166 --case 2169 --model deepseek-v4.1-flash-1017` on the base and on the head, one run at a time, run the head on the good cases for the ceiling, and run the first review of the head on the plans that the stage job staged for #5390 and #5422; give the results in a comment of the pull request
  - Verification: `$ uv run devops roadmap eval verify --case 2166 --case 2169 --model deepseek-v4.1-flash-1017 --dry-run`
