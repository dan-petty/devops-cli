# Proposal: #5884

## Why

The plan drift row removes the label `plan/needs-fix` from each plan pull request that has no drift problem (#5884). Three other checks write the same label: the model review of the stage job, the step fix-plan and a vet before a merge. So the row also removes a label that another check added, and the `stage_ready` row then marks a plan with an open finding ready. On #5876 the bot removed the label at 19:26:53Z on 2026-11-15 with no new commit, and again two minutes after a person added it back at 20:02:10Z. The row never wrote a drift comment on #5876.

## What Changes

- The drift comment holds the claim of the row on the label: `added` when the row added the label, `held` when another check held the label at the first round with problems, and `cleared` when the plan passes again.
- When a plan passes, the row changes an open claim to `cleared`. It removes the label only when the claim was `added` and the last plan comment of the item lists no open finding. A plan with no drift comment keeps its label.
- The row reads the drift comment of each plan on each round, one more request for each plan every 37 minutes.
- A consumer observes the label and the comment, so the change carries a spec delta.
- The change needs no new label. `stage_ready`, the implement job and the step fix-plan do not change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-drift`: the row removes only the label that it added, and it marks its comment when the plan passes again.

## Impact

- Code: `src/devops_cli/roadmap/stage/plan_drift.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_drift.py`

## Feasibility

Checked against `origin/main` at `ca62d6a9f`.

- `run_plan_drift` removes the label of every passing plan that holds it, with no check of the writer of the label.
- The events of #5876 show `labeled` by the Service at 19:01:43Z, `unlabeled` by the Service at 19:26:53Z, `labeled` by the owner at 20:02:10Z and `unlabeled` by the Service at 20:04:34Z. The pull request has no comment with the drift marker.
- `plan_comment` and `comment_open_findings` in `steps/fix_plan.py` already read the open findings of the last stage or fix-plan comment of an item. `roadmap/run.py` already imports `steps/fix_plan.py`, so the import adds no load time to the Service.

## Existing Tool Considered

GitHub labels hold no writer or reason, and no open tool tracks which check owns a shared label. The change keeps the claim in the drift comment that the row already writes. It adds no dependency. To build it costs about 30k tokens to write, about 1k tokens a month to keep, and about 1 hour of elapsed time. The change deletes `_update_comment`, whose work moves into `run_plan_drift`.
