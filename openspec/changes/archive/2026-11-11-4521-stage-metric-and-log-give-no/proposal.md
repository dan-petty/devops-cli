# Proposal: #4521

## Why

The stage job of the Service gives no reason when it leaves out an item (#4521). `stage_results` gives the result `skipped` to each left-out, returned and rejected item, and `devops_cli_roadmap_stage_total` has only the labels `result` and `repo`. The Service logs no left-out reason. So in 48 hours, four managed repositories were idle in each round, and only `devops roadmap explain` on a clone showed the three reasons.

## What Changes

- Each rule of the stage selection has a bounded kind, `LeftOutKind` in the new module `roadmap/stage/stage_left_out.py`. `LeftOut` holds the kind of its reason. The checks of the title and of the author are split, so each kind names one rule.
- `devops_cli_roadmap_stage_total` gets the label `reason`: the kind of a skipped item, `returned` or `rejected` for an item that the writes returned or rejected, and `none` for the other results.
- The Service logs one line for each left-out item with its kind and text, and logs it again only when the kind changes. The memory of the logged kinds is in the process, so a restart logs each reason one time more.
- This is a change of the behavior that a person observes (a metric label and a log line), so it has a spec delta.

## Capabilities

- `roadmap-stage`: ADDED requirement "A left-out item counts and logs its reason".

## Impact

- `src/devops_cli/roadmap/stage/stage.py`, the new `src/devops_cli/roadmap/stage/stage_left_out.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md` and `k8s/README.md`.
- The counter has a new label with at most 23 values for each repository. A dashboard or a query that sums by `result` gives the same totals.
- The change fits one pull request.

## Feasibility

Confirmed on origin/main 7234d718: `stage_results` (`src/devops_cli/roadmap/stage/stage.py`) maps each `plan.left_out`, `applied.returned` and `applied.rejected` item to `StageResult.SKIPPED`, and `emit_stage_results` emits only `result` and `repo`. `_Judge.reason` returns the first text of a list of checks, so each check gives one kind with no new judgment. `git grep -n "stage left out"` finds no log line. The issue holds the Prometheus and Loki queries that show the gap.

## Existing Tool Considered

The OTLP counter of the project (`emit` in `telemetry/instruments.py`) and the standard `logging` module, which the Service already uses, cover the label and the log line. The change adds no tool and deletes no code.
