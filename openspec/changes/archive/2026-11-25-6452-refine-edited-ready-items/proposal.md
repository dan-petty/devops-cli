# Proposal: #6452

## Why
`devops roadmap refine` does not look again at an open `Ready` item when a person edits its body outside the refine section or posts a trusted comment after its last refine round. The item keeps `status/ready` and its old Dependencies list, so `devops roadmap stage` can plan the item while a new blocker is open.

## What Changes
- Update `_refinable` so an open `Ready` item is selectable even when `unrefined_ready=False` if its text outside the refine section differs from `refine.body_hash` or a trusted person comment follows its last refine round.
- Add a trust predicate and comment reader parameter to `_refinable` (`comments_on` and `trusted`) so `_refinable` stays independent of the store while ignoring comments from bots and untrusted accounts.
- Update `refine_left_ready` and `devops roadmap explain` so the explanation reports when a `Ready` item is due for refine because a person edited the body outside the refine section or posted a trusted comment after the last round.
- Update `Seed` helpers and existing stale-hash test records (`tests/support/roadmap_refine.py` and `tests/roadmap/test_roadmap_explain.py`) to record real hashes matching the seeded outside body text.

## Capabilities
- `roadmap-refine/selection`: Select edited or commented open `Ready` items for re-refinement while ignoring bot comments and unchanged `Ready` items.
- `roadmap-explain`: Report an edited body outside the refine section or a new trusted comment as the reason refine is due on a `Ready` item.

## Impact
- `src/devops_cli/roadmap/refine/refine.py`
- `src/devops_cli/roadmap/explain.py`
- `src/devops_cli/lang/en/messages.py`
- `docs/roadmap/refine.md`
- `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `tests/roadmap/test_roadmap_explain.py`

## Feasibility
Confirmed against `origin/main` in `src/devops_cli/roadmap/refine/refine.py`:
- `_refinable` (`refine.py:3297`) selects `Ready` items only for `_is_unrefined_ready`, `_needs_second_look`, or `not is_approved(it)`.
- `is_approved` (`trust.py:54-61`) returns `True` without checking `refine.body_hash` when a person opened the item, and `_refinable` inspects no comments.
- `_apply_refined` (`refine.py:4526`) already returns an unready `Ready` item to `New` when `owns_status(r.item)` holds, and writes `refine.body_hash` and `refine.blocked_by`.

## Existing Tool Considered
The alternatives check on `#6452` returned `none` on 2026-11-19 and found no open tool that checks `refine.body_hash` outside the refine section or trusted comments after the last round. Estimated cost to build and maintain: about 40,000 tokens and about 1 hour.
