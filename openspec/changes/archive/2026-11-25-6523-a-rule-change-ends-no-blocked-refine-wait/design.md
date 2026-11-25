# Design

## Decisions
- Check `_set_by_older_rules(item, since)` in `_wait_still_on` for both `NextStep.PERSON` (`names_cause`) and `NextStep.BLOCKED`, and replace the `_set_by_older_rules` call inside `_person_wait_over` (or keep `_named_cause_ended` focused on causes) so both wait kinds use the same rules-version check without duplicate logic.
- Keep `_open_blockers` and cycle checks in `_still_waiting` before `_wait_state` so closed blockers and dependency cycles continue to exit early without reading comments.
- Update `docs/roadmap/refine.md:33` to match the code and specs: a rule change ends both person waits and blocked waits.

## Rejected alternatives
- Adding a separate rules-version record key for blocked waits: `RefineRecordKey.RULES` already records the rules version of every refined item.
- Checking `_set_by_older_rules` only when `RefineRecordKey.RULES` is present inside `NextStep.BLOCKED`: items without `RefineRecordKey.RULES` fall back to `commented_at`/`since`, matching `_person_wait_over`.
