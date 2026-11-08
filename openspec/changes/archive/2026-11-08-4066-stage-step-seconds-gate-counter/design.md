# Design

## Context

`devops_cli_roadmap_stage_total` counts the result of each item and has no step. `devops_cli_roadmap_row_seconds` (#4058) gives the seconds of a whole row. The stage row calls the model several times, and the gates run after each reply, so one slow step hides in the row total. The `emit()` function of `src/devops_cli/telemetry/instruments.py` sends the OTLP samples.

## Decisions

- **One histogram for all rows, with the labels `repo`, `row`, `step` and `result`.** #4067 sends the implement steps through the same instrument with `row` set to `implement`. Both changes use the same four labels, so a dashboard query groups by `row` and `step` and needs no second metric. The `step` values are `StepName` values. The gate and review steps exist only for the row `stage`, and the instrument text says so.
- **The row is an argument, not a shared scope.** The sites pass `row="stage"`, as `tool_metrics.start_run(row=...)` takes its row. No context variable carries the row.
- **The result is `ok` or `error`.** The issue gives these two values. Any exception that leaves the step is `error`; the exception goes on as before and the step swallows none. The values differ from the `success`, `error` and `stopped` of the row histogram on purpose: a step that a stop of the Service interrupts is an `error` of that step, and the row sample carries `stopped`.
- **One context manager `observe_step(repo, row, step)` in a new module `src/devops_cli/roadmap/step_metrics.py`.** It reads `clock.monotonic()` on entry and sends the sample in a `finally` block. The clock seam lets the tests set the seconds with the `clock` fixture. #4067 imports the same function.
- **The planner sends only when it knows the repository.** `_Planner` has `pull_repo`, which is empty for `plan_item`, the replay of the golden set. A replay sends no step sample and no refusal, so it adds no `repo` value to the series.
- **A sample is one call, not one item.** `plan` is each model call, `gate` is each call of `_problems`, and `review` is each model review. A refused reply adds a second plan sample and a second gate sample. The documentation states this.
- **`select` times `read_stage_selection` inside `plan_stage`.** `devops roadmap explain` calls `read_stage_selection` too, and it is not a stage round, so the timer is in `plan_stage` and not in the function.
- **A refusal is not an error.** `_problems` returns a list of problems, and the gate sample has the result `ok`. The result is `error` only when the gate code raises.
- **`_problems` calls `check_gates` and joins the lists.** The counter adds 1 for each gate with a non-empty list, in the order of `ProposalGate`, under the label `gate`. The join keeps the order that `check_proposal` uses, so the text of a refusal does not change. Only the stage job counts: the callers in `implement/implement.py` and `roadmap/plan_check.py` call `check_proposal` and send nothing. A gate with no problem adds no zero point.
- **`StepName` gains `SELECT`, `GATE` and `REVIEW` after `PLACE`.** They are metric labels. A failed review or gate still records the step `plan` in the ledger (`_failure_of`), so the stored string set does not change and no persisted file gets a field.
- **The series counts are in the text of the instruments.** The histogram text says "at most 10 series" (1 repository x 1 row x 5 steps x 2 results) for the stage row, and the counter text says "16 series" (1 repository x 16 gates). `docs/TELEMETRY.md` is generated from those texts.

## Rejected Alternatives

- **A label `lane` or `item` on the histogram.** An item number is unbounded, and the lane follows from the row. The label scheme of the row histogram has neither.
- **Wrap the gate call in `check_proposal`.** The implement step and the plan check call it too, and they are not a stage round. The gate name is only needed where the stage planner counts.
- **A second counter for the gate that found the most problems.** The issue asks for one count for each gate that found a problem, and the per-problem count adds no series but misleads: one gate can find many problems in one reply.
- **Count refusals per item.** The gates run several times for an item. A per-item count needs state across the rounds of one item and hides how often a gate refuses, which is the signal for a rule that the model cannot keep.
- **A try and finally block at each of the five sites.** It repeats the four labels at each site, and #4067 repeats them again. The context manager is the only helper the change adds.
- **Set `repo` to an empty string for a replay.** An empty label value adds a series. The planner sends nothing when it has no repository.
