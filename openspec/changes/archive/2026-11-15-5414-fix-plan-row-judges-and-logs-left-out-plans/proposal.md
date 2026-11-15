# Proposal: #5414 fix(roadmap): the fix_plan row judges and logs each plan it leaves out

## Why
Closes #5414.
The row `fix_plan` hides its queue, and a branch stop blocks it.
In mode `plan`, `select_fix_plan` logs only the first match and writes no attempt mark. It selects the same plan in each round and never names other plans in the queue.
A branch stop after selection is silent and writes no record. If a branch stop occurs, the row selects the same plan in each round, so no lower plan receives an attempt.

## What Changes
1. Move the branch check rules (`_branch_reason`) into `select_fix_plan` as ADR 0021 section 8 specifies. When a branch stop occurs on a candidate, log a warning, leave the candidate out with its reason, and continue evaluating subsequent candidates in the same round.
2. In mode `plan`, judge each candidate. Log the mode line that states that the row starts no attempt and names the plan that mode `on` would select, and log each left-out plan with its reason using `log_left_out`. The line repeats only when the reason of the item changes.

## Capabilities
- `roadmap.fix_plan`: Judge each candidate in mode `plan`.
- `roadmap.fix_plan`: Skip branch-stopped candidates with a warning and select the next candidate in the same round.
- `roadmap.fix_plan`: Log left-out plans with deduplicated reason tracking.

## Impact
- The `fix_plan` row in mode `plan` surfaces visibility into all candidate plans and reasons they are left out.
- A branch stop no longer stalls the row from processing subsequent eligible plans in the queue.

## Feasibility
Verified on origin/main:
- `select_fix_plan` returns at the first passing candidate (`src/devops_cli/roadmap/steps/fix_plan.py:618`).
- `_attempt` checks `_branch_reason` at line 1173 after selection and returns `FixPlanLeftOut`, which `_run_fix_plan_adapter` discards.
- Mode `plan` writes no `fix_plan.at`, so the lowest-numbered item is selected repeatedly without logging other items.

## Existing Tool Considered
The left-out log of the stage job (`stage_left_out.log_left_out`, #4521). No external tool or library needed.
