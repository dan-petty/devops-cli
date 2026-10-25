# Design

## Cross-Job Rule as the Single Trigger

Intake no longer triggers refinement directly. When `apply_intake` places a candidate, it performs only issue creation, label additions, card creation, and field updates. The cross-job rule in `src/devops_cli/roadmap/run.py` evaluates job outcomes after intake finishes. If intake placed an item at Priority P0, the rule marks the refine job due in the current round. Refine executes subsequently using its dedicated repository clone.

## Priority-Based Due Predicate

The cross-job rule checks whether intake placed an item with `CONST_ROADMAP_P0_PRIORITIES`. A critical fix is by definition a P0 item. Therefore, checking type labels such as `type/bug` or `type/security` is unnecessary and is removed from `run.py`. A non-P0 bug or security issue does not make refine due in the same round.

## Skip Finished Restored Cards

When `apply_intake` restores an archived card that already has a Priority set, it writes no fields and reports the card number in `IntakeApplied.finished`. The `_places_critical_or_p0` predicate skips candidates present in `IntakeApplied.finished`. Such cards do not constitute new placements and do not trigger refine in the round.

## Dead Code Removal

Intake was the only caller of `refine.refine_item`. With the hook deleted, `refine.refine_item` and its return type `RefineOutcome` become dead code. Both are removed from `src/devops_cli/roadmap/refine.py`.
