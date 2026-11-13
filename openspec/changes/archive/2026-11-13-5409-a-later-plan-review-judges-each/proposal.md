# Proposal: #5409

## Why

The model review of a plan does not converge in the stage job and in the step `fix-plan` (#5409). Each review is a new sample. It does not see the earlier findings or the answer of the planner. The planner fixes the earlier findings, and the next review opens a different finding on text that did not change. Then the stage and `fix-plan` decide on the counts of two independent reviews, so one weak new finding keeps `plan/needs-fix`.

- The open counts of the stage review rounds were 1, 2, 1 on #4472, 2, 1, 1 on #5118 and 5, 1, 1 on #5272. In each item the planner fixed the earlier findings, and then a different finding opened.
- Job `fix-plan-validate-4917-r2` logged "the review of the head found 1 open finding(s) before the repair, and the last review of the revision found 2". The result was `regated`, and the label stays on #4917.

Closes #5409.

## What Changes

- A later review gets the earlier open findings and the answer of the planner. From repair round 1 of the stage job, and in the first review of a `fix-plan` revision, the request holds `earlier` (each open finding of the review before: `number`, `type`, `where`, `problem` and `quote`) and `answer` (the texts of the plan that the revision added or changed, from a `difflib` diff of the lines of the two plans). The first review of a plan gets the same request and the same prompt as before.
- The reply of a later review has a second schema, `LaterVerification`: one verdict for each earlier finding (`holds` or `gone`) and the new findings. The task prompt `roadmap_stage_verify_later.md` follows the prompt of the pass only in a later review. It tells the reviewer to judge each earlier finding against `answer` and the plan, and to report a new finding only in a text of `answer`.
- An earlier finding that the review marks `holds`, or that gets no verdict, stays open. A new finding is open only when it is open by the rules of today and its quote is in a text of `answer`. A new finding on text that the revision did not change is advice: the comment lists it.
- `repair_round_due` gives a round past `roadmap.stage.verify_repair_rounds` while the last review marked more earlier findings `gone` than it opened new findings. It no longer compares the counts of two reviews. The line `stage review extended:` holds `fixed=<n> added=<n>` in place of `before=<n> open=<n>`.
- `fix-plan` keeps a revision that is not the same plan when its reviews fixed more open findings of the head than they added (`PlanRevision.fixed` and `PlanRevision.added`). It no longer compares the counts of two reviews. The case of `fix-plan-validate-4917-r2` (the review of the revision marks the finding of the head `gone` and opens one finding on unchanged text) is now `cleared`.
- The change has a spec delta: the request of a later review, the verdicts, the rule of a new finding, the extension rule and the rule of a kept revision are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: a later review judges each earlier open finding and opens a new finding only in changed text; the extension rule uses the verdicts.
- `roadmap-stage/fix-plan`: the first review of a revision judges the open findings of the head, and the step keeps a revision on the findings of the head that it fixed.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py` (`VerificationInput`, `LaterVerification`, `Verdict`, `Judgement`, `changed_texts`, `judge_later`, `repair_round_due`), `src/devops_cli/roadmap/stage/stage_toolbox.py` (`review_later`), `src/devops_cli/roadmap/stage/stage.py` (`PlanRevision`, `_verified`, `_review`, `_run_review`, `revise`), `src/devops_cli/roadmap/steps/fix_plan.py` (`_decide`), `src/devops_cli/roadmap/round_log.py`, the prompt `src/devops_cli/ai/tasks/roadmap_stage_verify_later.md`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/settings.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py` and the other tests whose fake verifier answers a later review.
- Documents: `docs/roadmap/stage.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` (generated from the setting).
- Cost: a later review reads about 1 k more input tokens (the earlier findings and the changed text). No new model call. The first review of a plan does not change, so the recall of the golden set of `devops roadmap eval verify` does not change.
- The Service runs the stage job and `fix-plan`, so the change takes effect with the next release of the Service image.

## Feasibility

- Source at `origin/main` 2daf63a6c (0.128.0): `VerificationInput.payload` (`stage_verify.py:213-221`) holds only `number`, `title`, `body`, `plan` and `files`. `repair_round_due` (`stage_verify.py:316-326`) returns `open_counts[-1] < open_counts[-2]` past the setting. `_decide` (`fix_plan.py:545-560`) keeps a revision only when `len(repaired.open_findings) < len(revision.before)`. `_Planner._verified` (`stage.py:1724-1773`) runs each review with `_input_of(target, change)`, which has no earlier finding, and `_Planner.revise` (`stage.py:1345-1404`) gives the revision to `_verified`, so its first review starts from zero too.
- The stage comments on #4472, #5118 and #5272 list open findings whose quotes come from the plan, from the issue and from repository files, read on 2026-11-13 with `devops gh api repos/dan-petty/devops-cli/issues/<n>/comments`.
- `StageProposal` (`stage_change.py:673-702`) has no key for an answer to each finding. The planner prompt (`roadmap_stage_change.md:1`) tells the planner to fix each finding at its place, or to show in `feasibility` with a quote of the inputs that it is no defect. Both answers are text that the revision adds or changes, so the changed text of the plan is the answer of the planner, and the planner schema does not change.
- The golden eval runs one first review for each case (`stage_verify_eval.py:271-291`, `review` of `stage_toolbox.py`), and this change keeps the request and the prompt of a first review byte for byte. A test proves it.

## Existing Tool Considered

`difflib.SequenceMatcher` of the Python standard library gives the changed text of the plan. Pydantic gives the reply schema of a later review, and the agent of `chat_structured` sends back a reply that fails it, as for each review. No open tool keeps the state of a review between rounds. Cost to build: about 1.2 M tokens and 4 hours. Keep: one payload key pair, about 1 k more input tokens for each review after the first. Fix: about 0.2 M tokens for each wrong verdict rule.

The decision point of step 3 of the issue (Jev judges a rebuttal of the planner, in mode `shadow`) is not in this change. #5215 adds the point `fix_plan.finding_check` with the question "Does this plan still hold this defect?", which is the same question for a rebuttal. One point serves both: #5215 can take each earlier finding with its verdict, `earlier` and `answer` as evidence. A point in mode `shadow` changes no decision, so this change loses no behavior.

## Dependencies

None. #5215 can reuse the verdicts (`Judgement.fixed`, `PlanRevision.fixed` and `PlanRevision.added`) and `changed_texts`. #5410 and #5411 change `open_findings` and the reply schema of the first review in other branches: the pull request that merges second adds its rule to `judge_later` too.
