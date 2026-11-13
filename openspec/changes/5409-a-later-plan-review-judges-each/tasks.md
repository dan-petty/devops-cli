# Tasks

## 1. A later review judges each earlier finding

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`. Creates: `src/devops_cli/ai/tasks/roadmap_stage_verify_later.md`.

- [x] 1.1 Write `test_a_later_review_gets_the_earlier_findings_and_the_answer`, `test_a_new_finding_outside_the_changed_text_is_advice`, `test_a_first_review_keeps_its_request_and_its_prompt`, `test_an_earlier_finding_with_no_verdict_holds`, `test_an_earlier_finding_that_holds_or_comes_again_stays_open`, `test_the_changed_text_is_each_block_of_new_or_moved_lines` and `test_a_round_past_the_setting_needs_more_fixed_than_added_findings` in `tests/roadmap/stage/test_roadmap_stage_verify.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `earlier` and `answer` to `VerificationInput`, `changed_texts`, `Verdict`, `LaterVerification`, `Judgement`, `verify_later`, `judge_later` and the prompt `roadmap_stage_verify_later.md`; give `repair_round_due` the last `Judgement`; add `review_later` to the toolbox
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_toolbox.py`

## 2. The stage and fix-plan decide on the verdicts

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/steps/fix_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, and the tests whose fake verifier answers a later review.

- [x] 2.1 Write `test_a_revision_that_fixes_the_head_finding_is_kept` in `tests/roadmap/steps/test_roadmap_fix_plan.py`, and `test_a_repair_round_sends_the_earlier_findings_and_the_answer` in `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`; change the tests of the extension to verdicts
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Give each later review of `_verified` the open findings of the review before and the plan before the repair; give the first review of a `fix-plan` revision the open findings of the head; log `fixed` and `added` on `stage review extended:`; add `PlanRevision.fixed` and `PlanRevision.added`, and keep a revision in `_decide` when it fixed more findings of the head than it added
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/steps tests/commands/test_roadmap_step_fix_plan.py tests/telemetry/test_roadmap_stage_steps.py tests/roadmap/refine`

## 3. Document the rule

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/roadmap/stage.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/config/settings.py`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [x] 3.1 Write the request of a later review, the verdicts, the rule of a new finding, the extension rule and the rule of a kept revision in `docs/roadmap/stage.md`, the stage row and the fix-plan row of `docs/CLUSTER.md`, the recall section of `docs/ROADMAP_WORKFLOW.md` and the description of `roadmap.stage.verify_repair_rounds`, and regenerate the documents of the settings
  - Verification: `$ uv run devops docs generate`

## Criteria

- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_verify.py::test_a_later_review_gets_the_earlier_findings_and_the_answer` passes: the payload of round 1 holds each open finding of round 0 and the answer of the planner.
- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_verify.py::test_a_new_finding_outside_the_changed_text_is_advice` passes.
- Group 2: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py::test_a_revision_that_fixes_the_head_finding_is_kept` passes: the head has 1 open finding, the review of the revision marks it `gone` and opens 1 finding on unchanged text, and the step keeps the revision.
- Groups 1 and 2: `uv run devops ci fail-to-pass --base origin/main` shows that the three tests fail on the base and pass on the head.
- Group 1: `uv run devops roadmap eval stage --replay` passes, and `test_a_first_review_keeps_its_request_and_its_prompt` shows that the request of the golden eval does not change, so its recall does not change.
- Pending a person: a validation table in a pull request comment replays the review rounds of #4472, #5118 and #5272 with the new payload, one model call at a time, with the columns item, round, open count before and open count after.

## Workflow follow-up

- #5215 adds the decision point that judges an earlier finding. It can use the verdicts of this change, and with `answer` as evidence it also judges a rebuttal of the planner (step 3 of #5409).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
