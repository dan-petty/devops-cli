# Proposal

## Why

The issue #4061 reports that refine and intake do not wait after a failure that the item did not cause.

Refine records only a failure that the item caused (`RefineFailure.item_caused`, #1526). A timeout or a dropped stream records nothing, so refine takes the same item again in every round while the cause lasts, and each round spends the model calls again.

Intake keeps what it decided in `IntakeRecord`. A candidate whose placement raised is decided again after the fresh ones. Each repeat costs a triage call and an embedding call. Intake keeps no class and no count for the failure.

The issues #4056 and #4060 gave the project one table of failure classes (`CLASS_BY_EXCEPTION`), one table of waits (`RETRY_AFTER`) and the function `retry_after`. The stage job uses them. This change makes refine and intake use the same tables.

## What Changes

- Add the members `investigate` (refine) and `place` (intake) to `StepName` in `src/devops_cli/roadmap/failure.py`. Add no second table of classes or waits.
- Refine. Add the keys `refine.failed_at`, `refine.failed_step` and `refine.failed_class` to `RefineRecordKey`. `RefineFailure` gets the field `failure_class`, from `failure_class_of(exc)`. `apply` writes the three keys for each failure except a placeholder failure, in the same marks write as the failed body hash when the item caused the failure. A timeout or a dropped stream now costs one marks write and no model call in the next rounds. The second failure on the same body settles the item to wait on a body edit and clears the three keys. `_Selection.consider` leaves the item out until `refine.failed_at` plus `retry_after(refine.failed_class)`. A body edit after a failure that the text caused ends the wait. `--item` overrules the wait. A round whose model call worked clears the three keys, as it clears `refine.failure`.
- Refine shows the wait as the step `retry` with the time after which the item is taken again, in the plan report and in `devops roadmap explain`.
- Intake. `IntakeRecord` gets the field `failed: dict[int, Failed]`. `Failed` holds the step, the class, the count and the time of the last failure. `PlacementFailure` gets the field `failure_class`. After `apply_intake`, and before the round raises for the failed placements, the record is written with the new entries: count 1 for a new failure, count plus 1 for a repeat, no entry for a candidate that placed. `plan_intake` gets the parameters `failed` and `now`, drops each candidate whose wait has not ended before it asks the model, and reports the numbers in `IntakePlan.held`. A held candidate makes no triage call and no embedding call, and does not make intake due. The poll and the webhook update both keep the record. `devops roadmap intake` keeps no record, so it waits for nothing.
- The item record gets no mark for an intake failure. `RoadmapItemChangedError` is no failure and records nothing.
- Not changed: `roadmap.alternatives.retry_days`; the rule that a placeholder failure records nothing (#3478); the rule that a failure the item did not cause leaves its text unmarked.
- The spec delta is behavior that a person sees in `explain`, in the record and in the number of model calls, so the change carries one.
- Rollout. The change removes, renames and tightens no setting. `RoadmapConfig` and the models of `roadmap.refine` and `roadmap.intake` ignore an unknown key (`extra='ignore'`), and the change adds no key to the example ConfigMap or to the live ConfigMap. So no ConfigMap change is needed before the image rolls, and no ConfigMap load test is needed. The intake record file is a file in the data directory of the Service, not a setting: a file from before this change loads with an empty `failed`, and a test holds this.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: A failed model call records its class and waits; A round whose model call worked clears the failed class
- `roadmap-intake-failures`: The intake record keeps the failure of a placement; A candidate with a recorded failure waits
- `roadmap-failure-taxonomy`: A step has a name
- `roadmap-explain`: Explain names a refine failure wait

## Impact

- Code: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/refine/test_roadmap_refine_failure_class.py`, `tests/roadmap/intake/test_roadmap_intake_failure_class.py`, `tests/roadmap/refine/test_roadmap_refine_failure_record.py`, `tests/roadmap/test_roadmap_failure.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/refine.md`, `docs/roadmap/intake.md`

## Feasibility

- I read the code at origin/main `bfe01926`. `StepName` has the members `plan` and `apply` only (`failure.py`). `CLASS_BY_EXCEPTION` maps `AIClientError` to `provider`, `StructuredOutputValidationError` to `parser` and `GitHubOperationError` to `ci_infra`. `RETRY_AFTER` has five keys, and `retry_after(recorded)` returns the wait of `ci_infra` for a missing or unknown class and never raises. So both jobs reuse the functions as they are. A model timeout is class `provider`, not `timeout`: `FailureClass.TIMEOUT` is in neither table.
- The issue says to write the keys in `_failure_marks`. That function takes a `JobFailure`, the result of a round whose model call worked (a form check or an open question). It has no exception and no class. The failures of the issue are `RefineFailure` values, made by `RefineFailure.of(item, exc)` and recorded by `_apply_result` and `_record_failure`. So the change writes the keys there, and uses `_failure_marks` only to clear them. The sentence "ride on the existing marks write" holds for a failure that the item caused. For a timeout there was no write before, so this change adds one marks write for each failed item. It replaces the model calls of the next rounds.
- A placeholder failure (`RefineFailure.placeholder`) is a fault of the model (#3478). Its rule is: no mark, no comment, and the next round asks the model again. This change keeps that rule, so the existing tests of #3478 stay valid.
- Intake: the failed placement is a `GitHubOperationError` raised by `apply_intake`, after the plan. The triage and embedding calls run in `plan_intake` before the apply. So the wait must drop the candidate from the queue in `plan_intake`, and the failure can be known only after `apply_intake`. In `run.py`, `_run_intake_adapter` writes `record.after(plan, now)` before the apply, and `_intake_one` (the webhook) merges before the apply. Both need a second write of the record after the apply and before `raise_for_failed_placements`.
- Settings: `RoadmapConfig` has `model_config` with `extra='ignore'` (`settings.py`), and the change adds no key. `IntakeRecord` is a frozen pydantic model with the default `extra='ignore'`, so an old file loads. I ran no code to prove this; the test `test_old_record_without_a_failed_field_loads_and_keeps_its_candidates` holds it.
- Tests: the new tests fail on `origin/main` for the right reason, run with `uv run devops ci test`: the intake file fails on the missing `IntakeRecord.failed`, `Failed` and `StepName.PLACE`, and the refine file fails on the missing `RefineRecordKey.FAILED_AT` and `RefineFailure.failure_class`. The record shows the run output path in the state file of this item.
- No upstream document or library is involved: the change reads project code only.

## Existing Tool Considered

No library covers a record of failure classes and waits. The tables of #4056 and #4060 (`CLASS_BY_EXCEPTION`, `RETRY_AFTER`, `retry_after`) are the open tool here, and the change reuses them. pydantic holds the record model (`Failed`), and the standard `datetime` holds the times. The change builds one small model, two record keys of three, and the wait check in two selections. Cost, as the issue states it: about 70,000 tokens and 3.5 hours to build, about 3,000 tokens a quarter to keep, and about 15,000 tokens and 1 hour to fix. The change deletes nothing of its own: it adds no table and no setting.

## Dependencies

The issues #4056 and #4060 are merged. The issue #4042 is merged.
