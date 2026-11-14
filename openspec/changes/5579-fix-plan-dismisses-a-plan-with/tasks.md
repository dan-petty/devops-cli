# Tasks

## 1. Let the severity alone decide which finding is open

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [ ] 1.1 `tests/roadmap/stage/test_roadmap_stage_verify.py` fails first: `test_a_major_other_finding_is_open` asserts that a quoted `other` finding of severity `major`, whose place the plan holds, is in `open_findings`, and that the same finding of severity `minor` is not
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` fails on the base
- [ ] 1.2 Add `DefectType.OTHER` and `DefectType.CONTRIVED_TEST` to `OPEN_TYPES` in `src/devops_cli/roadmap/stage/stage_verify.py`, so `OPEN_TYPES` holds the nine types that `VERIFY_TYPES` names. Preserve rule #3264 so a placeholder finding in a tool answer is not open. Update `test_the_open_types_are_the_seven_types_that_the_planner_can_fix`, `test_an_open_type_with_a_quote_in_the_input_is_open` and `test_an_open_finding_is_a_listed_type_or_a_placeholder_with_a_quote_in_the_input`. In `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, update `test_the_score_counts_recall_by_type_and_the_findings_on_good_plans` for `good_returning` count 2
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## 2. Make the two major contrived-test tests of the stage job a minor finding

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_verification.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_verification.py`.

- [ ] 2.1 Set `severity=Severity.MINOR` on the `contrived_test` finding of `tests/roadmap/stage/test_roadmap_stage_verification.py`: the `advice` line of `test_a_mixed_first_round_lists_every_finding_and_tells_the_planner_the_open_ones` and the answer of `test_a_contrived_test_finding_is_in_the_comment_and_the_draft_opens_and_stays_a_draft`. Rename the second test to `test_a_minor_contrived_test_finding_is_in_the_comment_and_the_draft_opens_and_stays_a_draft`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verification.py` passes

## 3. Keep the open types of the refine review narrow

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`. Changes: `src/devops_cli/roadmap/refine/refine_judge.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`.

- [ ] 3.1 `tests/roadmap/refine/test_roadmap_refine_trust.py` fails first: `test_a_major_other_finding_on_a_proposal_is_advice` gives a major `other` finding whose quote is in the proposal and whose place the proposal holds, and asserts the item is Ready with `refine.judge` `approved`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py` fails on the base
- [ ] 3.2 Replace the subtraction in `JUDGE_OPEN_TYPES` of `src/devops_cli/roadmap/refine/refine_judge.py` with an explicit `frozenset` of `DefectType.MISSING_PATH`, `DefectType.FALSE_PREMISE`, `DefectType.IGNORES_EXISTING_CODE` and `DefectType.SPEC_DELTA_WRONG`. Add a major `other` finding beside the advice finding of `tests/roadmap/refine/test_roadmap_refine_trust.py` and assert approval
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py` passes

## 4. Read both finding line forms of a plan comment

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/support/roadmap_fix_plan.py`, `tests/fixtures/roadmap_fix_plan/stage_comment.txt`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [ ] 4.1 `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails first: `test_the_reader_reads_a_finding_line_of_the_old_form` asserts that a line of the place `group 3 (and group 1)` reads as one finding of type `other`, severity `major`, part `tasks` and section `group 3 (and group 1)`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails on the base
- [ ] 4.2 Add `_OLD_FINDING_LINE` and `_OLD_PLACE_PARTS` to `src/devops_cli/roadmap/steps/fix_plan.py`, and a frozen `CommentFindings` with `findings` and `unreadable`. Make `comment_open_findings` try the current form through `_FINDING_LINE` and then the old form, take the part of an old place from its first word, and put each line that neither form reads into `unreadable`. Update tests in `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` passes

## 5. End an attempt on a line the step cannot read

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/support/roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [ ] 5.1 `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails first: `test_two_lines_the_reader_cannot_read_keep_the_label` seeds a stage comment with two lines that match neither form and asserts the result `unreadable_findings`, the label `plan/needs-fix` on the pull request, and the field `unreadable` of the result line with the value 2
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails on the base
- [ ] 5.2 Add `FixPlanResult.UNREADABLE_FINDINGS`, `FixPlanAttempt.unreadable` and `_unreadable_findings` to `src/devops_cli/roadmap/steps/fix_plan.py`. End the attempt with that result before `revise_plan` when the comment holds an unreadable line. Update `ROADMAP_FIX_PLAN_TOTAL` in `src/devops_cli/telemetry/instruments.py` and `messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` passes

## 6. Keep the label while the plan comment lists an open finding and repair comment defects

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `docs/roadmap/stage.md`, `tests/support/roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `docs/roadmap/stage.md`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [ ] 6.1 `tests/roadmap/steps/test_roadmap_fix_plan.py` fails first: `test_an_open_finding_of_an_old_form_comment_keeps_the_label` seeds a stage comment of the old form, answers the review of the head with no finding, and asserts the result `unchanged` with the label `plan/needs-fix` still on the pull request
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py` fails on the base
- [ ] 6.2 In `src/devops_cli/roadmap/stage/stage.py:revise`, check `if not before and not findings:` so open comment findings trigger `_repaired` instead of exiting early. In `_decide` of `src/devops_cli/roadmap/steps/fix_plan.py`, return `dismissed` only when `revision.before` is empty and comment findings are empty; else return `unchanged`. Update `test_a_clean_head_with_listed_findings_is_dismissed` in `tests/roadmap/steps/test_roadmap_fix_plan.py`, `test_a_head_that_its_review_finds_clean_loses_the_label_though_the_comment_lists_a_finding` in `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, and `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py tests/roadmap/steps/test_roadmap_fix_plan_comment.py` passes

## Criteria

- Group 6: A test with a stage comment of the old locator form gets no `dismissed` result, and the label stays (`devops ci fail-to-pass`).
- Group 1: A test with a major finding of type `other` gets a blocking result.
- Group 5: The result line of the step counts the lines that it could not read.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
