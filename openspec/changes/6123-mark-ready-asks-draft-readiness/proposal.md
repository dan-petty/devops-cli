# Proposal: #6123

## Why
The Service marked implement pull request #6041 (#3771) ready for review at 2026-11-17 04:04:10Z, and again at 04:48:58Z after an agent set it back to draft. Task group 5 of its `tasks.md` was not ticked both times. `devops pr ready 6041` refuses this state through `draft_readiness`, so one Service path marked the pull request ready without that decision (#6123).

The path is the plan branch of the watch row: `_apply_due_steps` in `src/devops_cli/roadmap/watch_row.py` called `mark_ready` for a green bot draft that `_find_plan_item` finds through `stage.pr`, with no `draft_readiness`. The record of #3771 holds 6041 as `stage.pr` and as `implement.pr`, because the implement job continued on the plan branch. The other paths ask `draft_readiness` themselves, so the defect was that `mark_ready` let any caller skip the one decision.

## What Changes
- `mark_ready` (`src/devops_cli/roadmap/steps/ready.py`) asks `draft_readiness` before it sends `gh pr ready`. An answer other than ready raises `RoadmapImplementError` with the reason, and sends nothing. A caller that holds the draft that it judged gives it; else `mark_ready` reads the draft with the new `read_ready_draft`: the pull request, the check runs of its head, and `read_draft`, which takes the kind from the record. Only the `--force` of a person skips the decision (`devops pr ready --force`, `devops roadmap step ready --force`; the second option was declared and not used).
- The watch row reads and judges a green plan draft before the Jev check and the mark. A refused head is kept in the ledger field `ready_head`, so the row judges that head once.
- Each other caller gives the draft that it judged: the implement job, the step `fix-checks`, the step `review` (through `read_ready_draft`), `devops pr ready`, and `stage_ready`, which now takes the kind from the record with `kind_of`.
- The behavior of the Service and of two commands changes, so the change carries spec deltas.

## Capabilities
- `pr-monitor`: the requirement "One mark-ready wrapper" adds the decision.
- `roadmap-watch-row`: a new requirement for the ready mark of a plan draft.

## Impact
- No path marks a draft ready that `draft_readiness` refuses. An implement pull request with a task that is not ticked stays a draft.
- The watch row sends three more reads (the pull request, the compare, the `tasks.md`) for a green plan draft, once for each refused head.
- The change fits one pull request.

## Feasibility
- Loki, `{namespace="devops", container="service"}` at 04:04:12Z: the webhook `pull_request` `ready_for_review` of devops-cli. No Job of #3771 ran at that time: the implement Job ended at 02:48Z (`limit_reached`) and the fix-checks Job at 03:22Z (`stopped`).
- Tempo, trace `f37612b9ebaa9e8f2439e686a6e9bc69`, span `service.job dan-petty/devops-cli` with `service.lane=watch`: a child span `subprocess.gh` with 6 arguments (`gh pr ready 6041 --repo dan-petty/devops-cli`) ran from 04:04:09.86Z to 04:04:10.82Z with exit 0. Trace `7c2ac6260fb20c6232818b974773ab9d` of the watch lane holds the same call at 04:48:56Z.
- The record of #3771 (`devops gh api repos/dan-petty/devops-cli/issues/3771`) holds `stage.pr` 6041, `implement.pr` 6041 and `stage.ready` 6041.
- Census of the callers: `git grep -n "mark_ready(" -- src/` gives 8 call sites (7 callers and the forward of `implement_pull.mark_ready`). The invariant test `tests/invariants/test_architectural_invariants.py` keeps `gh pr ready` in `steps/ready.py` only, so each path goes through `mark_ready`.

## Existing Tool Considered
No open tool decides when a roadmap draft is ready: `draft_readiness` is the project's one decision (ADR 0021 section 8, #5021), and GitHub has no rule that keeps a draft with unticked tasks in draft. The change moves the call of that decision into the one wrapper and deletes no code.
