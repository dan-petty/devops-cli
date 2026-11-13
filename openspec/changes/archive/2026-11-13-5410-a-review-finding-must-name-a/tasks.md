# Tasks

## 1. Name the place of a finding and check it against the plan

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/plan_read.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/fixtures/roadmap/plan_heads/5350-ccfbab2e9586/` (new), `tests/fixtures/roadmap_fix_plan/read_spec_5350.txt` (new).

- [x] 1.1 Write `test_a_finding_on_a_requirement_that_the_plan_does_not_hold_is_advice`, `test_a_finding_on_a_requirement_of_the_plan_stays_open`, `test_criterion_dropped_names_the_criterion_of_the_issue` and the tests of a group, a key, an issue text, a placeholder, a refine proposal, the prompt and the comment line in `tests/roadmap/stage/test_roadmap_stage_verify.py`, with the head ccfbab2e9586 of #5350 and its `read_spec` answer as fixtures; write `test_a_finding_whose_place_the_plan_does_not_hold_goes_to_the_comment_and_returns_nothing` in `tests/roadmap/stage/test_roadmap_stage_verification.py` and `test_a_finding_on_a_task_group_is_advice_because_a_proposal_has_no_task_groups` in `tests/roadmap/refine/test_roadmap_refine_trust.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `PlanPart` and `Locator`, make `Finding.where` a `Locator`, add `VerificationInput.holds`, and keep only a finding whose place the plan or the issue holds in `open_findings`; show the place with the templates `stage_finding_where` and `stage_finding_where_capability`; describe the place in the two prompts of the pass; give each test that builds a finding a place of its plan; run `uv run devops docs generate`, which leaves no diff
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/refine tests/roadmap/test_roadmap_failure.py`

## 2. Read the place back from a plan comment in fix-plan

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/support/roadmap_fix_plan.py`, `tests/fixtures/roadmap_fix_plan/stage_comment.txt`, `tests/fixtures/roadmap_fix_plan/stage_comment_2968.txt`, `tests/fixtures/roadmap_fix_plan/stage_comment_4472.txt`, `tests/fixtures/roadmap_fix_plan/stage_comment_4697.txt`.

- [x] 2.1 Make `test_the_reader_reads_back_each_open_finding_and_no_point` read a place of each part with a capability and brackets in its section, write `test_the_reader_leaves_out_a_line_whose_place_names_no_part`, and write the finding lines of the stage comment fixtures in the place form
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py`
- [x] 2.2 Read the part, the capability and the section of a finding line in `_FINDING_LINE` and `_finding_of` of `src/devops_cli/roadmap/steps/fix_plan.py`
  - Verification: `$ uv run devops ci test tests/roadmap/steps`

## 3. Describe the place rule

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/roadmap/stage.md`.

- [x] 3.1 Describe the place of a finding and the open rule in the review paragraph of `docs/roadmap/stage.md`
  - Verification: `$ uv run devops docs check`

## 4. Refuse a stored eval report in the old form

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_screen.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/stage/stage_screen_eval.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_eval_screen.py`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 Write `test_a_reviewer_report_in_an_old_form_exits_1_and_makes_no_request` in `tests/commands/test_roadmap_eval_screen.py`, with a stored report whose finding names its place as text
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_screen.py`
- [x] 4.2 Read each `--reviewer` report through `stored_cases`, which `resumed_outcomes` shares, so a report in the old form raises `ConfigurationError` with the name of the file; say in the message and in `docs/ROADMAP_WORKFLOW.md` that a new run gives a report in the new form
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_screen.py tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## 5. Apply the place rule in a later review

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`, `docs/roadmap/stage.md`.

- [x] 5.1 Write `test_a_new_finding_of_a_later_review_on_a_place_that_the_plan_does_not_hold_is_advice` and `test_an_earlier_finding_that_holds_keeps_its_place_when_the_revision_drops_it` in `tests/roadmap/stage/test_roadmap_stage_verify.py`, and `test_a_later_finding_on_a_requirement_that_the_plan_does_not_hold_keeps_the_revision` in `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_review_rounds.py`
- [x] 5.2 Say in the docstring of `judge_later` and in `docs/roadmap/stage.md` that a new finding of a later review follows the place rule and that an earlier finding keeps its locator
  - Verification: `$ uv run devops docs check`

## 6. Keep a place that names the other file, another form of a name or a criterion of refine

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/refine/refine_judge.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `docs/roadmap/stage.md`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`.

- [x] 6.1 Write `test_a_finding_that_names_the_design_for_a_key_of_the_proposal_stays_open` and `test_a_place_in_another_form_of_its_name_stays_open` with case 2166 of the golden set, `test_a_capability_with_a_space_or_a_bracket_is_refused` and `test_a_finding_on_a_criterion_of_a_refine_proposal_names_the_issue` in `tests/roadmap/stage/test_roadmap_stage_verify.py`, add heading forms to `test_a_finding_on_a_key_of_the_proposal_or_the_design_that_the_plan_holds_is_open`, write `test_the_reader_reads_back_a_section_with_brackets_and_no_capability` in `tests/roadmap/steps/test_roadmap_fix_plan_comment.py` and `test_a_finding_on_a_criterion_of_the_proposal_with_the_part_issue_refuses_the_item` in `tests/roadmap/refine/test_roadmap_refine_trust.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 6.2 Check the proposal and the design against one set of keys, compare names by their words, read the scenario names and the end segments of a capability, read `acceptance_criteria` for the part `issue`, refuse a capability that is not a capability name, end the section of a comment line at the first `): ` outside a pair of brackets, and say in the prompt and in `docs/roadmap/stage.md` which keys each file holds
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/steps tests/roadmap/refine`

## Criteria

- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that `test_a_finding_on_a_requirement_that_the_plan_does_not_hold_is_advice` fails on the base and passes on the head.
- Group 2: the replays of fix-plan read the open findings of the stage comment fixtures.
- Group 3: `uv run devops docs check` passes.
- Group 4: `devops roadmap eval screen --reviewer` with a report in the old form exits 1 and names the file.
- Group 5: `uv run devops ci fail-to-pass --base origin/main` shows that `test_a_new_finding_of_a_later_review_on_a_place_that_the_plan_does_not_hold_is_advice` fails on the base and passes on the head.
- Group 6: `uv run devops ci fail-to-pass --base origin/main` shows that `test_a_finding_that_names_the_design_for_a_key_of_the_proposal_stays_open` fails on the base and passes on the head.
- The eval: `uv run devops roadmap eval verify --case 2166 --case 2169 --model deepseek-v4.1-flash-1017` gives on the head a recall that is not lower than on the base, and the pull request comment gives both numbers. The base does not reach `CONST_ROADMAP_VERIFY_RECALL_FLOOR`, so the comparison shows only whether the prompt lowers the recall.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
