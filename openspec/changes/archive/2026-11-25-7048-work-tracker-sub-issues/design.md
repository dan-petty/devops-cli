# Design

## Decisions

- **Place `tracker_work` in `src/devops_cli/roadmap/dependencies.py`:** `dependencies.py` already owns tracker expansion (`_open_work`, `open_blockers`), reads from `stores.store` and `refine.refine`, and is not imported by `return_item.py` or `explain.py`, preventing cycles and duplicated child/blocker logic.
- **Guard trackers in `plan_return` (`src/devops_cli/roadmap/return_item.py`):** Check `item.is_tracker` in `plan_return` so both CLI previews (`return` without `--confirm`) and `--confirm` runs refuse returning a tracker. Query `store.open_items()` only inside the `if item.is_tracker:` refusal branch so non-tracker returns and `dry_run_return` (`tests/roadmap/test_roadmap_return.py:85-95`) preserve their exact single-issue read profile.
- **Keep existing `JobVerdict` outputs on `Explanation` (`src/devops_cli/roadmap/explain.py`):** Preserve `explained.refine` (`refine_left_tracker`) and `explained.stage` (`stage_left_tracker`) so `openspec/specs/roadmap-refine/selection/spec.md:167-169` and `test_a_new_tracker_gets_the_refine_tracker_text` (`tests/roadmap/test_roadmap_explain.py:809-822`) remain satisfied. Append tracker sub-issue and related-issue fields with empty tuple defaults at the end of `Explanation` and render them in `render_explanation` only when `is_tracker` is true.
- **Stay within `CONST_AGENTS_MD_MAX_CHARS` (`4,500`):** Shorten verbose wording in `AGENTS.md` lines 8 and 21 without touching any test-asserted phrase in `tests/invariants/test_agents_md.py`, keeping all rule titles in sync with `src/devops_cli/templates/AGENTS.md.j2`.

## Rejected alternatives

- **Checking `is_tracker` only in the CLI `return_cmd` (`src/devops_cli/commands/roadmap.py:1597-1631`):** Rejected because direct callers and tests of `plan_return` (`src/devops_cli/roadmap/return_item.py:43-64`) would still permit moving a tracker back to `status/new`, where `refine` (`src/devops_cli/roadmap/refine/refine.py:2494-2495`) ignores it.
- **Unconditionally fetching `store.open_items()` in `plan_return` or `dry_run_return`:** Rejected because `tests/roadmap/test_roadmap_return.py:85-95` asserts that a standard return dry run issues only the single `issues/{item}` read request.
- **Replacing `refine_left_tracker` text in `explain_item`:** Rejected because `openspec/specs/roadmap-refine/selection/spec.md:167-169` specifies `refine_left_tracker` verbatim as the refine verdict text for a tracker.
