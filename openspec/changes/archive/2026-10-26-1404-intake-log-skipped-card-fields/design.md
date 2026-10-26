# Design

## Context

During roadmap intake, candidate issues are planned first (`plan_intake`), which calls the model.
Later, `apply_intake` executes the planned writes.
During the planning window, a person may add the card to the board and assign field values or a milestone.
When `store.add_item` runs, it returns an `AddedItem` representing the existing board card.

## Field Reconciliation and Logging in `_on_card`

1. When `item.priority is not None`:
   - The card already holds a Priority, marking it as finished on the board.
   - `_on_card` drops all planned field writes (`decision.fields` and `decision.priority`).
   - `_on_card` logs `MESSAGES.roadmap.intake_skipped_fields` with the issue number and the comma-separated sorted list of all skipped fields.
   - `_on_card` returns `None`, causing `_apply_placement` to skip field and comment writes and record the issue in `IntakeApplied.finished`.

2. When `item.priority is None`:
   - `_on_card` reads `item.milestone or decision.subject.milestone`.
   - If a milestone is present and the plan had no milestone or was backlog, `placement` updates to `_resumed(kept)`.
   - `_on_card` filters `decision.fields` using `_unset(item, f, v)`.
   - The difference `{f.value for f, _ in decision.fields} - {f.value for f, _ in fields}` represents `held` fields whose planned writes are dropped.
   - If `held` is non-empty, `_on_card` logs `MESSAGES.roadmap.intake_skipped_fields` with the comma-separated sorted list of held fields.
   - `_on_card` updates `decision.reasons` to remove dropped fields so the reason comment omits them.
   - Returns the updated `IntakeDecision`.

## Message Format in `messages.py`

In `src/devops_cli/lang/en/messages.py`:
`intake_skipped_fields: str = "Intake skipped fields for #{number}: {fields}."`
Following ASD-STE100 rules:
- Active voice and simple past tense.
- Exact count of 6 words (under 25 words).
- Clear, unambiguous phrasing.

## Alternatives Considered

- Logging at `WARNING` level: Rejected because skipping fields that a person set on a card is intended behavior under ADR 0002 ("a job never reverts a person's change"), not an anomalous error state.
- Logging only `Priority` when `item.priority is not None`: Rejected because `_on_card` drops all planned writes (Status, Value, Effort, Priority). Omitting the other dropped fields from the log would mislead operators into believing those fields were written.
