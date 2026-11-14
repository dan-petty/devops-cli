# Tasks

## 1. Let the severity alone decide which finding is open

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`.

- [ ] 1.1 `tests/roadmap/stage/test_roadmap_stage_verify.py` fails first: `test_a_major_other_finding_is_open` asserts that a quoted `other` finding of the severity `major`, whose place the plan holds, is in `open_findings`, and that the same finding of the severity `minor` is not
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` fails on the base
- [ ] 1.2 Add `DefectType.OTHER` and `DefectType.CONTRIVED_TEST` to `OPEN_TYPES` in `src/devops_cli/roadmap/stage/stage_verify.py`, so `OPEN_TYPES` holds the nine types that `VERIFY_TYPES` names and the severity alone decides. Rewrite the comment above the constant to say that a type groups a finding and never keeps a blocker or a major finding out of the open set. Update `test_an_open_type_with_a_quote_in_the_input_is_open` and `test_an_open_finding_is_a_listed_type_or_a_placeholder_with_a_quote_in_the_input` of `tests/roadmap/stage/test_roadmap_stage_verify.py`, whose `contrived_test` finding is open now, and keep `test_a_minor_finding_is_advice` and `test_the_prompt_names_the_nine_types_and_no_other` as they are
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` passes

## 2. Make the two major contrived-test tests of the stage job a minor finding

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_verification.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_verification.py`.

- [ ] 2.1 Set `severity=Severity.MINOR` on the `contrived_test` finding of `tests/roadmap/stage/test_roadmap_stage_verification.py`: the `advice` line of `test_a_mixed_first_round_lists_every_finding_and_tells_the_planner_the_open_ones` and the answer of `test_a_contrived_test_finding_is_in_the_comment_and_the_draft_opens_and_stays_a_draft`. Rename the second test to `test_a_minor_contrived_test_finding_is_in_the_comment_and_the_draft_opens_and_stays_a_draft`, so each test still shows a finding that is advice, and keep the assertions of both
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verification.py` passes

## 3. Keep the open types of the refine review narrow

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`. Changes: `src/devops_cli/roadmap/refine/refine_judge.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`.

- [ ] 3.1 `tests/roadmap/refine/test_roadmap_refine_trust.py` fails first: `test_a_major_other_finding_on_a_proposal_is_advice` gives a major `other` finding whose quote is in the proposal and whose place the proposal holds, and asserts the item is Ready with `refine.judge` `approved`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py` fails on the base
- [ ] 3.2 Replace the subtraction in `JUDGE_OPEN_TYPES` of `src/devops_cli/roadmap/refine/refine_judge.py` with an explicit `frozenset` of `DefectType.MISSING_PATH`, `DefectType.FALSE_PREMISE`, `DefectType.IGNORES_EXISTING_CODE` and `DefectType.SPEC_DELTA_WRONG`, drop `OPEN_TYPES` from the import list, and rewrite the comment above it to say that the review of refine opens these four types and does not follow `OPEN_TYPES`. Add a major `other` finding beside the advice finding of `tests/roadmap/refine/test_roadmap_refine_trust.py` and assert the approval
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py` passes

## 4. Read both finding line forms of a plan comment

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/support/roadmap_fix_plan.py`, `tests/fixtures/roadmap_fix_plan/stage_comment.txt`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [ ] 4.1 `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails first: `test_the_reader_reads_a_finding_line_of_the_old_form` asserts that a line of the place `group 3 (and group 1)` reads as one finding of the type `other`, the severity `major`, the part `tasks` and the section `group 3 (and group 1)`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails on the base
- [ ] 4.2 Add `_OLD_FINDING_LINE` and `_OLD_PLACE_PARTS` to `src/devops_cli/roadmap/steps/fix_plan.py`, and a frozen `CommentFindings` with `findings` and `unreadable`. Make `comment_open_findings` try the current form through `_FINDING_LINE` and then the old form, take the part of an old place from its first word, and put each line that neither form reads into `unreadable`. Change `_attempt` to pass `listed.findings` to `revise_plan` and to count `len(listed.findings)`. Update each reader test in `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` to read `.findings`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` passes

## 5. End an attempt on a line the step cannot read

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`.

- [ ] 5.1 `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails first: `test_two_lines_the_reader_cannot_read_keep_the_label` seeds a stage comment with two lines that match neither form and asserts the result `unreadable_findings`, the label `plan/needs-fix` on the pull request, and the field `unreadable` of the result line with the value 2
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` fails on the base
- [ ] 5.2 Add `FixPlanResult.UNREADABLE_FINDINGS`, `FixPlanAttempt.unreadable` and `_unreadable_findings` to `src/devops_cli/roadmap/steps/fix_plan.py`. End the attempt with that result before `revise_plan` when the comment holds an unreadable line: keep the label, post no comment, log one line for each line that it could not read through `safe_text`, write the result mark, and report the count `unreadable` in the result line. Add the two messages to `src/devops_cli/lang/en/messages.py`, give `_detail` its branch, and name the result in the module docstring and in the docstring of `FixPlanResult`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` passes

## 6. Keep the label while the plan comment lists an open finding

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/support/roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`.

- [ ] 6.1 `tests/roadmap/steps/test_roadmap_fix_plan.py` fails first: `test_an_open_finding_of_an_old_form_comment_keeps_the_label` seeds a stage comment of the old form, answers the review of the head with no finding, and asserts the result `unchanged` with the label `plan/needs-fix` still on the pull request
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py` fails on the base
- [ ] 6.2 Filter the findings of the last plan comment to `OPEN_SEVERITIES` in `_attempt` and give them to `_decide` through `_settle`. Return `dismissed` only when `revision.before` is empty and that filtered tuple is empty; else return `unchanged`. Update the docstring of `_decide` and the `dismissed` paragraph of the module docstring of `src/devops_cli/roadmap/steps/fix_plan.py`, and update the test of `tests/roadmap/steps/test_roadmap_fix_plan.py` that asserts the dismissal of a head with only a minor finding
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py` passes

## Criteria

- Group 6: A test with a stage comment of the old locator form gets no `dismissed` result, and the label stays (`devops ci fail-to-pass`).
- Group 1: A test with a major finding of type `other` gets a blocking result.
- Group 5: The result line of the step counts the lines that it could not read.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
