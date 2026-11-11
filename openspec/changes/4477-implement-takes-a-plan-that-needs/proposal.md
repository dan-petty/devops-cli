# Proposal

## Why

The implement job takes a Staged item while the draft pull request of its plan holds the label `plan/needs-fix`. The stage job sets the label when the model review of the plan finds an open finding (`_label_needs_fix` in `src/devops_cli/roadmap/stage/stage.py`, constant `PLAN_NEEDS_FIX_LABEL` in `src/devops_cli/roadmap/stage/stage_verify.py`). The row `stage_ready` keeps such a draft a draft, but `_Judge._pull_reason` in `src/devops_cli/roadmap/implement/implement.py` accepts every open draft. On 2026-11-10 the Service started a runner Job for #3443 6 minutes after its plan #4352 got the label, and for #3451 7 minutes after its plan #4353 got the label. Both Jobs stopped on `limit_reached`, and each spent its step budget on a plan that the review refused (#4477).

## What Changes

- `_Judge._pull_reason` leaves out an open draft that holds `PLAN_NEEDS_FIX_LABEL`, with a reason that names the label and the pull request. The judge reads the labels from the `PullStatus` that it reads already, so the change adds no request. The judge keeps such items, and `ImplementPlan.needs_fix` returns them.
- The row `implement` of the Service logs each such item once for each draft. The round records the draft in the new mark `implement.needs_fix`, and returns only the items that it did not record yet. A round that judges the item and does not leave it out for the label clears the mark, so a new label is logged again.
- When the label is gone, the judge takes the item again, because it reads the label in each round.
- `docs/roadmap/implement.md` and the record table of `docs/ROADMAP_WORKFLOW.md` name the reason and the mark.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job leaves out a Staged item whose draft holds the label `plan/needs-fix`

## Impact

- Code: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/support/roadmap_implement.py`
- Settings: none. The live ConfigMap needs no change.

## Feasibility

- `devops gh api repos/dan-petty/devops-cli/issues/4352/events` showed the label `plan/needs-fix` set by the App at 2026-11-10T10:51:32Z and removed by a person at 13:47:05Z. The same read of #4353 showed 11:40:27Z and 14:16:43Z.
- `kubectl -n devops get jobs` showed `devops-cli-runner-20261110-105724-b626` (args `roadmap implement --item 3443 --confirm`, start 10:57:29Z) and `devops-cli-runner-20261110-114742-c187` (args `--item 3451`, start 11:47:47Z). `kubectl -n devops logs` of both showed `Failure class limit_reached. Action left: raise_limit.` and `stopped 1`.
- `grep -rn "needs-fix\|NEEDS_FIX" src/devops_cli/roadmap/implement/` found nothing. `_label_needs_fix` in `stage.py` sets the label, and `_settle` in `stage_ready.py` reads it from `PullStatus.labels`.
- `_Judge._pull_reason` in `implement.py` reads `PullStatus` with `client.get_pull_status` and checks only `is_open_draft`. `PullStatus.labels` in `src/devops_cli/github/client.py` holds the label names.
- `run_implement_round` in `implement_submit.py` calls `plan_implement` for the Service, and the runner Job calls it with `--item`, so one check in the judge covers both.
- First check: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/implement/test_roadmap_implement_submit.py`.
- Second check: `uv run devops openspec check`.

## Existing Tool Considered

The change uses the label that the stage review sets already, the `PullStatus` that the judge reads already, and the record marks of the store. `stage_ready.py` uses the same pattern for `stage.needs_fix`: it tells about the label once and records the draft. No open tool decides which roadmap item a job takes. Written cost: about 30k tokens to build, keep and fix, and 1.5 hours of elapsed time.
