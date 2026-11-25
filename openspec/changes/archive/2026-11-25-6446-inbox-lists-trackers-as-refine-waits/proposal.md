# Proposal

## Why
Issue `#6446`: `devops roadmap inbox` and `has_person_cause` report refine waits (`refine`, `split`, `alternatives`, `failed`) and open owner questions for tracker items (`type/epic` or `sub_issues > 0`). Refine already skips trackers, so stale refine or owner keys on a tracker stay in the inbox as permanent waits and inflate `devops_cli_roadmap_inbox_items`.

## What Changes
- Exclude `item.is_tracker` items in `refine_wait_on_person`, `_split_lines`, `_alternatives_lines`, `_failed_lines`, and `_owner_lines` in `src/devops_cli/roadmap/inbox.py`.
- Ignore refine and owner-question record keys in `has_person_cause` (`src/devops_cli/roadmap/phase.py`) when `item.is_tracker` is true.
- Update `docs/roadmap/inbox.md` to document tracker exclusion for refine waits and owner questions.
- Add tests in `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_gauges.py`, and `tests/roadmap/test_roadmap_phase.py`.

## Capabilities

### New Capabilities
- `roadmap-inbox`: exclude tracker items from `refine`, `split`, `alternatives`, `failed`, and `owner` lines and counts.
- `roadmap-phases`: ignore refine and owner-question causes in `has_person_cause` for tracker items.

## Impact
- `src/devops_cli/roadmap/inbox.py`
- `src/devops_cli/roadmap/phase.py`
- `docs/roadmap/inbox.md`
- `tests/roadmap/test_roadmap_inbox.py`
- `tests/roadmap/test_roadmap_inbox_gauges.py`
- `tests/roadmap/test_roadmap_phase.py`
