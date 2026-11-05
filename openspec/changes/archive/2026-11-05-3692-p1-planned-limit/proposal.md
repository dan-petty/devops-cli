# Proposal

## Why

Issue #3692: `roadmap.stage.planned_limit` (default 20, #3487) stops the stage job, and the last selection rule lets only `P0-Critical` items pass. On 2026-11-05, about 39 to 41 items were Planned against the limit of 20, and delivery runs at about 2 items a day. So the count will not fall below the limit soon. The stage job opened no plan for an item below P0 while the limit held, and at 14:24Z the rule left out 23 of 69 Ready items. A count by label gives 0 Ready `P0-Critical` items and 11 Ready `P1-High` items, so the rule lets no Ready item pass now. The owner approved the change on 2026-11-05: keep the limit, and let P1 items pass it as P0 items pass it now.

## What Changes

- At the limit, the stage job takes an item with the priority `P0-Critical` or `P1-High`. It leaves out each other item with the reason of the limit, and that reason names the two priorities.
- The limit, its default and the `--item` rule stay. The change adds no setting.
- `devops roadmap explain` gives the new reason, because it judges the item with the function that the job calls. `devops roadmap inbox` names the two priorities in its line.
- The change alters a selection rule and two output texts, which a consumer observes, so it carries spec deltas in `roadmap-stage`, `roadmap-explain` and `roadmap-inbox`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the setting and the rule of the limit.
- `roadmap-explain`: the reason of the limit, and the verdict for a P1 item.
- `roadmap-inbox`: the line that states the limit.

## Impact

- `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/inbox.py`.
- `tests/roadmap/test_roadmap_stage_selection.py`, `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_limit_classes.py`.
- `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/inbox.md`, `k8s/README.md`, `k8s/devops/configmap.example.yaml`, and the generated documents.
- Refine does not change: #3502 owns refine, and #3633 holds the text about refine.

## Feasibility

- `_Judge._queue_full` (`src/devops_cli/roadmap/stage.py`) is the one rule. `select_stageable` calls it for the job, and `explain_item` reads the same selection. `explain.py` and `commands/roadmap.py` only pass the number of the limit, so they need no change of rule. `inbox.py` states the rule in one text.
- `uv run devops gh api 'search/issues?q=repo:dan-petty/devops-cli+is:issue+is:open+label:status/ready+label:priority/p1-high'` and the same query for each status and priority gave, on 2026-11-05: Ready 0 P0-Critical, 11 P1-High, 58 P2-Medium, 1 P3-Low; Planned 0 P0-Critical, 1 P1-High, 34 P2-Medium, 2 P3-Low.
- The archived change `2026-11-04-3487-stage-planned-limit` gives no reason against this change. It lets `P0-Critical` pass because its issue asks for that. Its reason for the limit is that a plan that waits long meets a changed default branch, and that reason stays true for each P1 plan. Its design bounds the overshoot by `roadmap.stage.limit`. Items that pass the limit were already outside that bound. With P1 items the effect is larger, because the intake model can set `P1-High` and cannot set P0, so `docs/roadmap/stage.md` now states that no setting bounds these items.

## Existing Tool Considered

No outside tool applies. The change uses the rule `_queue_full` and the priority constants of `src/devops_cli/config/constants.py`. It adds one constant and one small function, and it deletes the comparison with `CONST_ROADMAP_CRITICAL_PRIORITY` in `stage.py`.
