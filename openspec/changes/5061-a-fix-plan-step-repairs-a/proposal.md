# Proposal: A fix-plan step repairs a plan pull request with open findings

## Why

Closes #5061. The stage job keeps a plan pull request in draft with the label `plan/needs-fix` when an open finding of its verification review remains after the repair rounds (#3264). After that, no job repairs the plan. The stage job does not select a staged item again, the implement job leaves a `plan/needs-fix` draft out, and the row `stage_ready` refuses a green draft that holds the label. `docs/roadmap/stage.md` says that "a later stage round that finds no open finding removes the label", but no row runs such a round. On 2026-11-12 six open plan pull requests held the label: #4849, #4917, #4963, #4980, #5032 and #5053.

## What Changes

- A new step `fix-plan` (`src/devops_cli/roadmap/steps/fix_plan.py`) repairs one open plan pull request that holds `plan/needs-fix`, for each call:
  - **Selection.** An open item with the Status Ready and a recorded stage pull request (a Staged item), no runner Job and no claim of an agent or a person. Its pull request is an open draft that holds the label, and its branch holds no commit of a person. The item has fewer than 2 attempts on the head of the pull request, its last attempt is 6 hours old or older, and the step pushed fewer than 3 revisions to the pull request. The highest priority goes first, and one call takes at most 1 plan.
  - **Repair.** The step reads the plan of the head with the plan reader (`read_change`) and gives it to the stage planner at the latest default branch (`stage.revise_plan`). The gates check that plan, and the verification pass reviews it. The planner gets the plan as `previous` and each open finding as `problem`. The revision goes through the gates and the normal verification repair rounds.
  - **Writes.** When the revision has fewer open findings than the plan of the head, the step writes the change folder as one commit on the default branch and pushes it to the branch with `--force-with-lease` on the head that it read. It also sets the title and the body of the pull request when they change. With no open finding left, it removes the label. When the review of the head finds no open finding, the step only removes the label. Else the step records the attempt and writes nothing more to GitHub.
  - **Marks.** The record keys `fix_plan.key` (`<pull>:<head>`), `fix_plan.attempts`, `fix_plan.revisions`, `fix_plan.at` and `fix_plan.result`. The step writes the attempt marks before the model call, so a stop of the Service counts the attempt. One comment with the marker `<!-- devops roadmap fix-plan -->` follows each attempt that changes the plan or the label.
  - **Observability.** One result line for each attempt (`log_job_result`, job `fix_plan`), with the counts of the attempt and the open findings before and after, and the counter `devops_cli_roadmap_fix_plan_total` by repository and result.
- A new command `devops roadmap step fix-plan` in a new group `devops roadmap step`. Without `--confirm` it prints the plan pull request that it selects, calls no model and writes nothing. `--confirm` runs the attempt. `--item` names one item for a run by hand. `--dry-run` makes no request.
- A new row `fix_plan` of the model lane of the Service, after `stage`, due every 53 minutes and on a first run. The setting `roadmap.fix_plan.mode` is `off`, `plan` or `on`, and it starts in `plan` (ADR 0021, section 8, rule 5). Mode `plan` logs the selection and writes nothing. The rows `stage_ready` and `pr_conflicts` stay.
- `stage.py` gets the seam `revise_plan` and the planner method `revise`. They call the existing functions of the planner (`_request`, `_returned`, `_review`, `_repaired` and `_verified`), and they add no planner or verifier code.
- ADR 0021 section 8 and ADR 0022 section 2 get the row `fix-plan`.
- The change has a spec delta: the command, its messages, the row and the writes to GitHub are observable.

## Capabilities

- New: `roadmap-stage/fix-plan`.

## Impact

- The Service runs the row in mode `plan` until a person sets `roadmap.fix_plan.mode: on` in the ConfigMap of the Service. Then each attempt spends at most the model limits of one stage item: 13 planner calls and 3 review calls with the default `roadmap.stage.gate_returns`, plus one review and one repair of the head plan.
- The model lane gets one more row. A round with no selected plan reads the issues of the store, which the lane already holds, and one pull request for each Staged item that the bounds do not leave out.
- The change fits one pull request.

## Feasibility

- `src/devops_cli/roadmap/stage/stage_verify.py:84` defines `PLAN_NEEDS_FIX_LABEL`. `stage.py` `_label_needs_fix` adds it when the last review has an open finding. `_verified` returns the plan to the planner only for a finding of `RETURN_TYPES`, so a plan with only `criterion_dropped` or `spec_delta_wrong` findings stays open (`origin/main` 2e6f407f0).
- `stage.py` `select_stageable` leaves out an item with a staged branch, `implement.py:485` leaves out a draft with the label, and `stage_ready.py:141` keeps such a draft a draft. No row or command removes the label, except a stage round of the same item, which the selection does not start.
- `devops gh api repos/dan-petty/devops-cli/pulls/<n>` on 2026-11-12: #4849, #4917, #4963, #4980, #5032 and #5053 are open drafts with `plan/needs-fix`. The stage comments of their items name the open types `criterion_dropped`, `ignores_existing_code`, `false_premise`, `task_order`, `verify_form`, `missing_path` and `spec_delta_wrong`.
- `src/devops_cli/roadmap/plan_read.py` `read_change` reads a change folder back as a `StageProposal`, as `plan_check.py` and `implement.py` do. The stage writer deletes the plan record of an item when it stages the item (`StageWriter`), so the plan of the branch is the only copy of the plan.
- `src/devops_cli/roadmap/service_stop.py` `raise_if_service_stops` is the drain guard (#4925). `src/devops_cli/roadmap/job_result.py` `log_job_result` writes the result line (#4845).
- ADR 0021 section 8 gives the rules of a new row: own keys and own marked comments, mode `off`, `plan` or `on` that starts in `plan`, the marker read first, and the inner limit first.

## Existing Tool Considered

No open tool repairs an OpenSpec plan from the findings of this project's verification pass. The step reuses the stage planner, its gates and its verification pass, the plan reader, `clone_git`, the pull request labels of the store, the result line, the drain guard and git `--force-with-lease`. It deletes no code. Cost to build: about 1.5M agent tokens and 1 agent-day. Keep: about 0.1M tokens a month. Fix until it matches a tool: no tool exists.
