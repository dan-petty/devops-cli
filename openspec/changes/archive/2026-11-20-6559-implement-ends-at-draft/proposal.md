# Proposal: #6559

## Why

The owner decided on 2026-11-20 that the implement Job ends at "draft pull request opened" (#2695, comment 7047676083). The split of #3702 gives the agent phase no App key, so the agent can make no work-in-progress push and the Job can run no watch of the checks. The Service watch row marks a draft ready, and the fix-checks Jobs repair a failed check. This is part A of #3702 (comment 7049207841). Closes #6559.

## What Changes

- The implement Job ends when the draft holds the final title and body. It records `implement.result` as `drafted`, sets Status In Review and comments the spend. It runs no watch, no repair after the push, no evidence comment and no `gh pr ready`.
- A step makes no `wip:` commit, and a stopped step resets to the commit where it started. `implement_wip.py`, `_keep`, `_move_wip`, the records `implement.wip` and `implement.continued`, and the counter `devops_cli_service_kept_work_total` go.
- The ready path of the step `fix-checks`, which the watch row runs, takes a delivery draft with `implement.result` equal to `drafted`.
- The intended result of the `implement` result line is `drafted`, a new baseline.
- The setting `roadmap.implement.monitor_timeout_seconds` goes with the watch.

## Capabilities

- `roadmap-implement-job/pull-request`, `repair`, `record`, `stops`, `runner-job`, `deadline`: the run ends at the draft, and the WIP and watch requirements go.
- `roadmap-implement-step/exit-checks`, `model-calls`, `roadmap-implement-runner`: no `wip:` commit.
- `roadmap-watch-row`, `roadmap-fix-checks`: the ready path takes a drafted draft.
- `roadmap-explain`, `roadmap-service-counters`, `github-session-timeouts`, `metric-instruments`: no kept work, no kept-work counter, no monitor bound, no `watch` step sample.
- `roadmap-implement-step/budgets`, `roadmap-service-deployment`: no `monitor_timeout_seconds`.

## Impact

- A failed check of a class other than `test`, `lint`, `types` and `plan_defect` gets no repair. Before, the Job repaired a failed check whose log named a path of the repair scope, whatever its class.
- A pod that dies loses the work of the group that runs. A checkpoint still keeps each group that passed.
- The `implement` success ratio is not comparable with the ratio before this version.
- The live ConfigMap needs no change first: `RoadmapImplementConfig` ignores a key it does not know (`extra="ignore"`), so `monitor_timeout_seconds` in the ConfigMap does no harm. The example ConfigMap drops it.

## Feasibility

- `src/devops_cli/roadmap/watch_row.py` (`_ready_after_fix`) and `src/devops_cli/roadmap/steps/fix_checks.py` (`_ready_after_repair`) took only a draft with `fix_checks.result` equal to `repaired`. Without the change no Service code marks a green implement draft ready. The new tests fail before the change and pass after it.
- The watch row starts fix-checks only for `FIX_CHECK_CLASSES` (`src/devops_cli/roadmap/steps/watch.py`).

## Existing Tool Considered

No tool is needed: the change deletes code and reuses the watch row and the step `fix-checks`. It deletes `implement_wip.py` (240 lines), the watch and ready code of `implement_run.py` and `implement_pull.py`, the kept-work counter, and their tests.

The change fits one pull request.
