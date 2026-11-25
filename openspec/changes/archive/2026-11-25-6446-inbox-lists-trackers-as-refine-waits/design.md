# Design

## Decisions
1. Filter `item.is_tracker` in `src/devops_cli/roadmap/inbox.py` across `refine_wait_on_person`, `_split_lines`, `_alternatives_lines`, `_failed_lines`, and `_owner_lines`. Because `_refine_lines` delegates to `refine_wait_on_person` and `inbox_gauges` counts lines returned by `read_inbox`, filtering at those five functions removes tracker waits from both human output and `devops_cli_roadmap_inbox_items`.
2. Gate refine and owner-question checks inside `has_person_cause` (`src/devops_cli/roadmap/phase.py`) on `not item.is_tracker`, leaving execution-phase stop keys (`ImplementRecordKey.STOPPED`, `StageRecordKey.NEEDS_SPLIT`, `StageRecordKey.NEEDS_FIX`, `verdict/fix-plan`) intact.
3. Reuse the `Item.is_tracker` property instead of duplicating `sub_issues > 0 or CONST_ROADMAP_EPIC_LABEL in labels`.

## Rejected alternatives
- Scrubbing stale refine keys off GitHub tracker bodies during refine: refine already skips trackers early, so an inbox-side filter stops stale tracker records immediately without extra GitHub writes.
- Checking `CONST_ROADMAP_EPIC_LABEL` or `sub_issues` inline at each call site: duplicates `Item.is_tracker`.
