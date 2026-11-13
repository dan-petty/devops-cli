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

## Criteria

- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that `test_a_finding_on_a_requirement_that_the_plan_does_not_hold_is_advice` fails on the base and passes on the head.
- Group 2: the replays of fix-plan read the open findings of the stage comment fixtures.
- Group 3: `uv run devops docs check` passes.
- Pending a person: run `uv run devops roadmap eval verify` on the base and on the head with the same cases and model, and compare the recall of the blocker and major defects. The base does not reach `CONST_ROADMAP_VERIFY_RECALL_FLOOR`, so the comparison shows only whether the prompt lowers the recall.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
