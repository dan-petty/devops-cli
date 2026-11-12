# Proposal: #5150

## Why

The step `fix-plan` compares the open findings of two different model reviews (#5150). The count before the repair comes from the last plan comment, which the stage job wrote with an earlier review at an earlier commit. The count after the repair comes from the last review of the revision in the attempt. Two reviews of one plan can find different counts, so the result `unchanged` or `revised` does not show whether the revision is better than the plan of the head.

The first live attempt, on #4980 of item #2530 with release 0.119.0, ended `unchanged: 1 open finding(s) before the repair, 2 after it`. One review of the same head plan with the same verification model and prompt found 2 open findings, not 1. The stage comment did not list one of them (`verify_form`), so the first repair did not get it.

Closes #5150.

## What Changes

- In each attempt, the verification pass reviews the plan of the head at the latest default branch. The open findings of that review are the count before the repair, and the step compares the last review of the revision with it.
- The planner gets each open finding of that review and each open finding of the last plan comment. The comment findings do not count.
- A head plan with no open finding in that review loses the label with no plan call, as in a later stage round.
- The result line and the report of the command show the count of the comment (`comment`) beside `before` and `after`.

## Capabilities

- Modified: `roadmap-stage/fix-plan` (the repair, the review of the head, the result line).

## Impact

- `src/devops_cli/roadmap/stage/stage.py` (`_Planner.revise`), `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`.
- `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`.
- An attempt on a plan whose comment lists a finding makes one more review run: about 3.3M tokens, 96% of them cache reads, and 9 minutes on #4980. An attempt whose head review is clean makes no plan run.
- The change fits one pull request.

## Feasibility

- Source: `_Planner.revise` at 0.119.0 sets `before = list(findings)` from the comment and reviews the head only when the comment lists none; `_settle` in `fix_plan.py` pushes only when `after < before`.
- Live run: Job `devops/fix-plan-validate-4980` printed `1 open finding(s) before the repair, 2 after it`. The Tempo trace `aa2875702bd3ac1a86127683a8e86a4d` holds 9 agent runs (6 plan runs, 3 reviews) whose tokens add up to the reported 15,933,306.
- Baseline: one review of the head `89b5e650822f` with `deepseek-v4.1-flash-1017` (the model of the Service ConfigMap), the code of 0.119.0 and the default branch `22176a02be18` found 2 open findings (`false_premise`, `verify_form`) and 2 points (`other`). The stage comment of the same plan lists 1 (`criterion_dropped`).
- The verification prompts and the open types did not change between the release that wrote the comment and 0.119.0 (`git diff 87ae9eefa f77ce3dd7`), so the difference comes from the review sample and the commit.

## Existing Tool Considered

No open tool applies: the defect is the comparison rule of the step. The change reuses `_Planner._review`, the call that the step already made when no comment listed a finding. Cost to build: about 0.4M agent tokens and 1 hour. Keep: none beyond the step.
